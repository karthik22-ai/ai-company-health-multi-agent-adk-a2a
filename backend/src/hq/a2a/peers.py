"""Agent-to-agent communication over the A2A protocol (a2a-sdk).

Every question or hand-off between two agents is a real A2A `message/send` call to the *other* agent's A2A endpoint
(`/a2a/<agent_id>/`, served by `host.py`). By default the HTTP client uses an in-process ASGI transport, so the full
protocol stack (agent card, JSON-RPC/HTTP binding, task lifecycle) is exercised without opening sockets; set
HQ_A2A_TRANSPORT=http to call real URLs instead – the same code can then talk to remote A2A agents.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from typing import Any

import httpx
from a2a.client import Client
from a2a.client.client_factory import ClientConfig, ClientFactory
from a2a.types import Message, Part, Role, SendMessageRequest

from hq.agents.personas import peer_prompt, task_prompt
from hq.agents.roster import AGENTS
from hq.core.config import Settings
from hq.core.world import Task, World

log = logging.getLogger("hq.a2a")


def extract_text(resp: Any) -> str:
    """Pull plain text out of a StreamResponse (message, task, or status/artifact update)."""
    chunks: list[str] = []

    def parts_text(parts: Any) -> None:
        for p in parts:
            if p.text:
                chunks.append(p.text)

    if resp.HasField("message"):
        parts_text(resp.message.parts)
    if resp.HasField("task"):
        for art in resp.task.artifacts:
            parts_text(art.parts)
        if not chunks and resp.task.status.HasField("message"):
            parts_text(resp.task.status.message.parts)
    if resp.HasField("artifact_update"):
        parts_text(resp.artifact_update.artifact.parts)
    if resp.HasField("status_update") and resp.status_update.status.HasField("message"):
        parts_text(resp.status_update.status.message.parts)
    return "\n".join(chunks).strip()


class A2APeers:
    def __init__(self, settings: Settings, world: World, remote_agents: dict[str, str] | None = None):
        self.settings = settings
        self.world = world
        self.remote = remote_agents or {}          # agent_id -> base URL of an external A2A agent
        self.http: httpx.AsyncClient | None = None
        self._clients: dict[str, Client] = {}
        self.messages: deque[dict[str, Any]] = deque(maxlen=300)
        self.runtime: Any = None                    # set by the app (needed to run hand-off tasks)

    # ------------------------------------------------------------------ transport
    def bind_asgi(self, app: Any) -> None:
        self.http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://hq.local", timeout=600)

    def bind_http(self) -> None:
        self.http = httpx.AsyncClient(timeout=600)

    async def aclose(self) -> None:
        for c in self._clients.values():
            try:
                await c.close()
            except Exception:  # pragma: no cover
                pass
        if self.http:
            await self.http.aclose()

    def url_for(self, agent_id: str) -> str:
        if agent_id in self.remote:
            return self.remote[agent_id].rstrip("/")
        base = "http://hq.local" if self.settings.a2a_transport == "asgi" else self.settings.base_url
        return f"{base}/a2a/{agent_id}"

    async def _client(self, agent_id: str) -> Client:
        if agent_id not in self._clients:
            assert self.http is not None, "A2APeers transport not bound"
            factory = ClientFactory(ClientConfig(httpx_client=self.http, streaming=False))
            self._clients[agent_id] = await factory.create_from_url(self.url_for(agent_id))
        return self._clients[agent_id]

    # ------------------------------------------------------------------ protocol calls
    async def send_text(self, to_id: str, text: str, *, context_id: str | None = None) -> str:
        client = await self._client(to_id)
        msg = Message(message_id=uuid.uuid4().hex, role=Role.ROLE_USER, parts=[Part(text=text)])
        if context_id:
            msg.context_id = context_id
        last = ""
        async for resp in client.send_message(SendMessageRequest(message=msg)):
            t = extract_text(resp)
            if t:
                last = t
        return last

    def _record(self, kind: str, frm: str, to: str, request: str, response: str, started: float) -> None:
        self.messages.appendleft({"ts": time.time(), "kind": kind, "from": frm, "to": to, "request": request[:500],
                                  "response": response[:800], "ms": int((time.time() - started) * 1000)})

    async def ask(self, frm: str, to: str, question: str) -> str:
        """A colleague asks another a question (A2A request/response). Shown in the UI as speech bubbles + a message flying over."""
        w = self.world
        started = time.time()
        w.say(frm, f"Asking {AGENTS[to].name.split()[0]}: {question}", 4000)
        w.handoff(frm, to, f"❓ {question[:40]}", assign=False)
        try:
            answer = await self.send_text(to, peer_prompt(AGENTS[frm].name, question), context_id=f"peer-{frm}-{to}")
        except Exception as e:  # peer unreachable – tell the caller instead of crashing the task
            log.warning("A2A ask %s -> %s failed: %s", frm, to, e)
            self._record("consult", frm, to, question, f"ERROR {e}", started)
            return f"(could not reach {to}: {e})"
        w.say(to, answer, 5000)
        w.handoff(to, frm, "💬 answer", assign=False)
        w.convo(frm, to, "a2a", question)
        w.convo(to, frm, "a2a", answer)
        self._record("consult", frm, to, question, answer, started)
        return answer

    async def hand_off(self, frm: str, to: str, item: str, instructions: str) -> Task:
        """Pass work to a colleague: creates a task for them, flies the document across the UI, and has *them* run it over A2A."""
        w = self.world
        task = w.new_task(to, item, instructions, source=f"a2a:{frm}")
        w.handoff(frm, to, item, assign=False)
        w.say(frm, f"📤 {item} → {AGENTS[to].name.split()[0]}", 3000)
        w.convo(frm, to, "handoff", f"📤 {item}: {instructions}")
        asyncio.create_task(self._run_handed_off(frm, to, task), name=f"handoff-{task.id}")
        return task

    async def _run_handed_off(self, frm: str, to: str, task: Task) -> None:
        w, started = self.world, time.time()
        try:
            async with w.locks[to]:                 # an agent works on one task at a time; others stay queued ("todo")
                w.start_task(task)
                payload = {"task_id": task.id, "title": task.title, "instructions": task.instructions, "handed_off_by": frm}
                if self.settings.use_mock:
                    payload["_mock"] = {"final_note": f"Delivered to {AGENTS[frm].name.split()[0]}"}
                result = await self.send_text(to, task_prompt(payload, AGENTS[frm].name), context_id=f"task-{task.id}")
                t = w.tasks[task.id]
                w.convo(to, frm, "handoff", f"✅ {task.title}: {(result or '')[:1200]}")
                if t.status not in ("done", "blocked"):
                    w.finish_task(t, result)
                else:
                    t.result = result
                self._record("hand_off", frm, to, f"{task.title}: {task.instructions}", result, started)
                w.say(to, f"✅ {task.title} done", 3000)
                w.handoff(to, frm, f"✅ {task.title}", assign=False)
        except Exception as e:
            log.exception("hand-off %s failed", task.id)
            w.fail_task(task, str(e))
            self._record("hand_off", frm, to, task.title, f"ERROR {e}", started)
