"""ADK runtime: RUNS the agents the factory builds (agents/factory.py): tasks, chats, talks, enquiries, meeting replies, presentations."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from hq.agents.personas import CHAT_MARK, chat_prompt, present_prompt, task_prompt
from hq.agents.roster import AGENTS, AgentSpec
from hq.core.config import Settings
from hq.core.world import Task, World
from hq.llm.guarded import FOREGROUND, foreground
from hq.quality.traces import Trace

log = logging.getLogger("hq.runtime")
RUN_TIMEOUT = 240.0            # the owner is waiting (chat, talk)
BACKGROUND_TIMEOUT = 900.0     # workflows and residents: background calls are paced to stay inside the Vertex AI quota


class AgentRuntime:
    def __init__(self, settings: Settings, world: World, peers: Any):
        self.settings, self.world, self.peers = settings, world, peers
        self.sessions = InMemorySessionService()
        self.agents: dict[str, LlmAgent] = {}
        self.runners: dict[str, Runner] = {}
        self.chat_runners: dict[str, Runner] = {}
        from hq.agents.factory import AgentFactory
        self.factory = AgentFactory(settings, world, peers, runtime=self, sessions=self.sessions)
        for spec in self.factory.all_employees():
            self.add_employee(spec)

    # ------------------------------------------------------------------ agents come from the factory
    def add_employee(self, spec: AgentSpec) -> None:
        """Create (or re-create) an employee's work and chat agents: at start-up and when People & Culture hires someone."""
        work, chat, run, chat_run = self.factory.employee(spec)
        self.agents[spec.id], self.runners[spec.id], self.chat_runners[spec.id] = work, run, chat_run

    def _resident_runner(self, rid: str) -> Runner:
        return self.factory.resident(rid)

    def market_block(self) -> str:
        return self.factory.market_block()

    # ------------------------------------------------------------------ low level
    async def _run(self, runner: Runner, user_id: str, session_id: str, text: str) -> str:
        msg = types.Content(role="user", parts=[types.Part(text=text)])
        out: list[str] = []
        tr = Trace(runner.agent.name, session_id, text, FOREGROUND.get())

        async def go() -> None:
            async for ev in runner.run_async(user_id=user_id, session_id=session_id, new_message=msg):
                tr.event(ev)
                if ev.is_final_response() and ev.content and ev.content.parts:
                    t = "".join(p.text or "" for p in ev.content.parts if getattr(p, "text", None))
                    if t:
                        out.append(t)

        try:
            await asyncio.wait_for(go(), RUN_TIMEOUT if FOREGROUND.get() else BACKGROUND_TIMEOUT)
        except BaseException as e:
            tr.finish(self.world, "\n".join(out), e)
            raise
        tr.finish(self.world, "\n".join(out))
        return "\n".join(out).strip()

    # ------------------------------------------------------------------ tasks
    async def run_task(self, task: Task, *, sender: str | None = None, mock: dict[str, Any] | None = None,
                       context: dict[str, Any] | None = None) -> str:
        """Run one task on its agent (serialised per agent). Returns the agent's final text. Never raises: failures mark the task failed."""
        w = self.world
        payload: dict[str, Any] = {"task_id": task.id, "title": task.title, "instructions": task.instructions}
        if context:
            payload["context"] = context
        if self.settings.use_mock and mock:
            payload["_mock"] = mock          # scripted behaviour for the offline mock; real Gemini never sees it
        async with w.locks[task.agent]:
            w.start_task(task)
            try:
                try:
                    text = await self._run(self.runners[task.agent], "hq", f"task-{task.id}", task_prompt(payload, sender))
                except (asyncio.TimeoutError, TimeoutError):
                    log.warning("task %s timed out, retrying once", task.id)
                    w.say(task.agent, "⏳ Model was slow – retrying…", 3000)
                    text = await self._run(self.runners[task.agent], "hq", f"task-{task.id}-retry", task_prompt(payload, sender))
            except Exception as e:
                log.exception("task %s failed", task.id)
                w.fail_task(task, f"{type(e).__name__}: {e}")
                return ""
            cur = w.tasks[task.id]
            w.remember(task.agent, "task", f"Task '{task.title}': {(text or '').strip()[:240]}", 0.6)
            if cur.status == "blocked":
                cur.result = text
            elif cur.status != "done":
                w.finish_task(cur, text)
            else:
                cur.result = text
            return text

    # ------------------------------------------------------------------ chat with the user
    def history(self, who: str, n: int = 10) -> str:
        """Conversation buffer: the last exchanges between the owner and this person (kept in the database, so it survives restarts)."""
        rows = [m for m in self.world.thread(who, "ceo", 2 * n) if m["channel"] == "chat"][-2 * n:]
        return "\n".join(f"{'Owner' if m['frm'] == 'ceo' else 'You'}: {m['text'][:400]}" for m in rows)

    async def chat(self, agent_id: str, text: str, history: str | None = None) -> str:
        try:
            self._chat_n = getattr(self, "_chat_n", 0) + 1     # a fresh session each turn: the conversation buffer is in the prompt
            with foreground():
                reply = await self._run(self.chat_runners[agent_id], "user", f"chat-{agent_id}-{self._chat_n}", chat_prompt(text, self.history(agent_id) if history is None else history))
        except Exception as e:
            log.exception("chat with %s failed", agent_id)
            return f"(I couldn't answer just now: {type(e).__name__})"
        return reply or "…"

    # ------------------------------------------------------------------ town residents
    async def run_resident(self, rid: str, reason: str) -> str:
        """One shopping decision by a town resident. Never raises."""
        from hq.agents.personas import shopping_prompt
        town = self.world.company.town
        r = town.resident(rid)
        if not r:
            return ""
        self._town_n = getattr(self, "_town_n", 0) + 1
        try:
            return await self._run(self._resident_runner(rid), "town", f"town-{rid}-{self._town_n}", shopping_prompt(r, reason))
        except Exception as e:  # noqa: BLE001
            log.exception("resident %s failed", rid)
            return f"(could not decide: {type(e).__name__})"

    async def talk(self, who: str, text: str) -> str:
        """You (the CEO) talk to anyone: an employee or a town resident. Both sides go into their memory and the conversation log."""
        with foreground():                             # the owner is waiting: these model calls go before background work
            return await self._talk(who, text)

    async def _talk(self, who: str, text: str) -> str:
        w = self.world
        hist = self.history(who)                       # read the buffer before logging the new message
        w.convo("ceo", who, "chat", text)
        if who.startswith("r"):
            r = w.company.town.resident(who)
            if not r:
                return "(no such resident)"
            prompt = (f"{CHAT_MARK} The owner of AI Company Health (a health insurer in your town) is talking to you. Reply as yourself in 1-4 sentences "
                      "of plain text (no markdown), honestly, from your own life, home, job, health insurance and memories. You don't have to buy anything."
                      + (f"\nYour conversation with them so far (oldest first):\n{hist}" if hist else "") + "\nUSER: " + text)
            self._town_n = getattr(self, "_town_n", 0) + 1
            try:
                reply = await self._run(self._resident_runner(who), "town", f"talk-{who}-{self._town_n}", prompt) or "…"
            except Exception as e:  # noqa: BLE001
                log.exception("talk to %s failed", who)
                reply = f"(couldn't answer: {type(e).__name__})"
            w.emit({"type": "town_event", "event": {"resident": who, "kind": "talk", "text": reply[:200]}, "say": reply[:90], "quiet": True})
        else:
            reply = await self.chat(who, text, hist)
            w.chat_reply(who, reply)
        w.convo(who, "ceo", "chat", reply)
        w.remember(who, "talk", f"The owner said: \"{text[:200]}\" and I replied: \"{reply[:200]}\"", 0.7)
        return reply

    async def resident_task(self, rid: str, text: str, mock_mode: str) -> str:
        import json as _json
        self._town_n = getattr(self, "_town_n", 0) + 1
        try:
            return await self._run(self._resident_runner(rid), "town", f"rtask-{rid}-{self._town_n}",
                                   text + "\nTASK_JSON: " + _json.dumps({"resident": rid, "_mock": {"biz": mock_mode}}))
        except Exception as e:  # noqa: BLE001
            log.exception("resident task %s failed", rid)
            return f"(failed: {type(e).__name__})"

    async def enquiry(self, agent_id: str, resident: dict[str, Any], question: str) -> str:
        """A member of the public asks an employee a question (the employee answers with their own tools)."""
        prompt = (f"{CHAT_MARK} A member of the public, {resident.get('name')} ({resident.get('age')}, {resident.get('suburb')}), contacts you about health "
                  "insurance. Answer as yourself in 2-4 sentences, honestly and helpfully, using real plan and price information from your tools. Never ask "
                  "about or use their health conditions to price or select (community rating); you can explain what each plan covers.\nUSER: " + question)
        try:
            return await self._run(self.chat_runners[agent_id], "town", f"enq-{resident.get('id')}-{agent_id}", prompt) or "Thanks for calling - let me send you our plan summary."
        except Exception as e:  # noqa: BLE001
            log.exception("enquiry to %s failed", agent_id)
            return f"(the line is busy: {type(e).__name__})"

    async def meeting_reply(self, agent_id: str, room: str, agenda: str, transcript: str, ask: str) -> str:
        """An attendee answers in a meeting when it is their turn to speak (raise-hand queue)."""
        prompt = (f"{CHAT_MARK} You are in a meeting in {room}. Agenda: {agenda or 'open discussion'}.\nConversation so far (most recent last):\n{transcript}\n"
                  "It is now your turn to speak. Answer the CEO in 2-4 sentences as yourself, with real numbers from your tools where useful. "
                  "If a colleague should answer part of it, say so and mention them with @Name.\nUSER: " + ask)
        try:
            return await self._run(self.chat_runners[agent_id], "user", f"meet-{room}-{agent_id}", prompt) or "Noted - I'll come back with the numbers."
        except Exception as e:  # noqa: BLE001
            log.exception("meeting reply by %s failed", agent_id)
            return f"(I'll follow up on that after the meeting: {type(e).__name__})"

    # ------------------------------------------------------------------ presentation for the user
    async def slides(self, agent_id: str) -> list[dict[str, Any]]:
        """Ask the agent to summarise its work as slides; fall back to a deterministic slide built from the world state."""
        try:
            raw = await self._run(self.chat_runners[agent_id], "user", f"present-{agent_id}-{id(object())}", present_prompt())
            data = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))  # type: ignore[union-attr]
            slides = [s for s in data.get("slides", []) if isinstance(s, dict) and s.get("title")]
            if slides:
                return [{"title": str(s["title"]), "bullets": [str(b) for b in s.get("bullets", [])][:4],
                         "progress": s.get("progress")} for s in slides[:3]]
        except Exception as e:
            log.info("slides for %s via LLM failed (%s); using fallback", agent_id, e)
        return [self.fallback_slide(agent_id)]

    def fallback_slide(self, agent_id: str) -> dict[str, Any]:
        t = self.world.current_task(agent_id)
        done = [x for x in self.world.tasks.values() if x.agent == agent_id and x.status == "done"][:3]
        spec = AGENTS[agent_id]
        if t:
            return {"title": t.title, "bullets": [b for b in [t.note] if b] or ["In progress"], "progress": t.progress}
        return {"title": f"{spec.role}: status", "progress": None,
                "bullets": [f"Completed: {x.title}" for x in done] or ["No active work right now"]}
