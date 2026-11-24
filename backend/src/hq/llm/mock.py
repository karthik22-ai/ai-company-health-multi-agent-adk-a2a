"""A deterministic stand-in for Gemini, used when no GOOGLE_API_KEY is configured (and in tests).

It plugs into ADK exactly like a real model: it receives an LlmRequest and answers with function calls (which ADK
executes against the real tools) and finally text. It never fabricates facts: its answers are built from what the
tools return.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from hq.agents.personas import CHAT_MARK, PEER_MARK, PRESENT_MARK, TASK_MARK
from hq.llm import mock_biz


def _text_of(content: types.Content) -> str:
    return " ".join(p.text for p in (content.parts or []) if getattr(p, "text", None))


def _system_text(req: LlmRequest) -> str:
    si = getattr(req.config, "system_instruction", None)
    if si is None:
        return ""
    if isinstance(si, str):
        return si
    if hasattr(si, "parts"):
        return _text_of(si)
    return str(si)


def _fc(name: str, **args: Any) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


class MockLlm(BaseLlm):
    model: str = "mock-gemini"
    owner: str = ""
    step_delay: float = 1.0          # seconds of "thinking" per step (scaled per flow); 0 in tests
    _sys: str = ""

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"mock-.*"]

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        delay = self.step_delay
        contents = llm_request.contents or []
        # the latest *user text* message (function responses are user-role too, but carry no text)
        idx = max((i for i, c in enumerate(contents) if c.role == "user" and _text_of(c)), default=-1)
        user_text = _text_of(contents[idx]) if idx >= 0 else ""
        after = contents[idx + 1:] if idx >= 0 else []
        calls = [p.function_call.name for c in after for p in (c.parts or []) if p.function_call]
        responses = [p.function_response for c in after for p in (c.parts or []) if p.function_response]
        tools = set((llm_request.tools_dict or {}).keys())
        self._sys = _system_text(llm_request)
        agent_id = (re.search(r"AGENT_ID:\s*(\S+)", self._sys) or [None, "agent"])[1]

        if TASK_MARK in user_text:
            await asyncio.sleep(delay * 0.7)
            parts = self._task(user_text, calls, responses)
        elif user_text.startswith(CHAT_MARK):
            await asyncio.sleep(delay * 0.3)
            parts = self._chat(user_text, calls, responses, tools)
        elif user_text.startswith(PRESENT_MARK):
            await asyncio.sleep(delay * 0.3)
            parts = self._present(calls, responses)
        elif user_text.startswith(PEER_MARK):
            await asyncio.sleep(delay * 0.3)
            parts = self._peer(user_text, calls, responses, agent_id)
        else:
            parts = [types.Part(text="Understood.")]
        from hq.llm import usage
        prompt_chars = sum(len(_text_of(c)) for c in contents) + len(self._sys)
        usage.record(self.owner or agent_id, prompt_chars // 4, sum(len(p.text or '') + 40 for p in parts) // 4)
        yield LlmResponse(content=types.Content(role="model", parts=parts))

    # ------------------------------------------------------------------ task flow
    def _task(self, text: str, calls: list[str], responses: list[Any]) -> list[types.Part]:
        payload = json.loads(text.split(TASK_MARK, 1)[1].strip())
        mock = payload.get("_mock", {})
        if mock.get("biz"):
            agent = (re.search(r"AGENT_ID:\s*(\S+)", self._sys) or [None, "agent"])[1]
            return mock_biz.next_action(mock["biz"], agent, calls, responses, mock)
        title = payload.get("title", "task")
        plan: list[tuple[str, dict[str, Any]]] = [
            ("set_status", {"state": "working", "text": title}),
            ("update_progress", {"percent": 15, "note": f"Started: {title}"}),
        ]
        if mock.get("consult"):
            c = mock["consult"]
            plan.append(("consult_peer", {"peer_id": c["peer_id"], "question": c["question"]}))
        plan.append(("update_progress", {"percent": 45, "note": mock.get("midpoint_note", "Analysis in progress")}))
        blocker = mock.get("blocker")
        if blocker:
            plan.append(("report_blocker", {"reason": blocker}))
        else:
            plan.append(("update_progress", {"percent": 75, "note": "Reviewing results"}))
            if mock.get("handoff"):
                h = mock["handoff"]
                plan.append(("hand_off_work", {"peer_id": h["peer_id"], "item": h["item"],
                                               "instructions": h.get("instructions", "Please take it from here.")}))
            plan.append(("update_progress", {"percent": 100, "note": mock.get("final_note", "Completed")}))
            plan.append(("set_status", {"state": "done", "text": f"Done: {title}"}))
        n = len(calls)
        if n < len(plan):
            name, args = plan[n]
            return [_fc(name, **args)]
        if blocker:
            return [types.Part(text=f"Blocked on '{title}': {blocker}")]
        consulted = ""
        for r in responses:
            if r.name == "consult_peer" and isinstance(r.response, dict):
                consulted = f" Input from {r.response.get('peer')}: {str(r.response.get('answer', ''))[:160]}"
        lines = [f"Completed '{title}'.", mock.get("final_note", ""), consulted.strip()]
        return [types.Part(text="\n".join(x for x in lines if x))]

    # ------------------------------------------------------------------ chat flow
    def _chat(self, text: str, calls: list[str], responses: list[Any], tools: set[str]) -> list[types.Part]:
        user = text.split("USER:", 1)[-1].strip().lower()
        if not calls:
            if re.search(r"(come|go|join|head).*(meeting|room)|\bdemo\b|show me", user) and "go_to_room" in tools:
                room = (re.search(r"\b(mr[123]|brd)\b", user) or [None, "mr1"])[1]
                return [_fc("go_to_room", room_id=room)]
            if re.search(r"\b(desk|go back|return)\b", user) and "return_to_desk" in tools:
                return [_fc("return_to_desk")]
            if "get_my_status" not in tools:
                return [_fc("my_profile")] if "my_profile" in tools else [types.Part(text="Hello!")]
            return [_fc("get_my_status")]
        r = responses[-1] if responses else None
        resp = (r.response if r is not None else {}) or {}
        if r is not None and r.name == "my_profile":
            return [types.Part(text=f"Hi, I'm {resp.get('name', 'a local')}, {resp.get('age', '')}. I work as {str(resp.get('occupation', 'a local')).lower()} and I'm on "
                                    f"{resp.get('current_cover', 'no cover')}. What would you like to know?")]
        if r is not None and r.name == "go_to_room":
            return [types.Part(text=resp.get("message", "On my way."))]
        if r is not None and r.name == "return_to_desk":
            return [types.Part(text="Heading back to my desk.")]
        task = resp.get("task")
        if re.search(r"block|stuck|issue|problem", user):
            return [types.Part(text=(f"Yes — I'm blocked: {resp.get('text')}." if resp.get("state") == "blocked" else "No blockers on my side."))]
        if task:
            pct = f" — {task['progress']}% done" if task.get("progress") is not None else ""
            note = f". {task['note']}" if task.get("note") else ""
            return [types.Part(text=f"I'm on “{task['title']}”{pct}{note}.")]
        return [types.Part(text=f"I'm {resp.get('state', 'idle')} right now and have no active task. How can I help?")]

    # ------------------------------------------------------------------ presentation flow
    def _present(self, calls: list[str], responses: list[Any]) -> list[types.Part]:
        if not calls:
            return [_fc("get_my_status")]
        st = (responses[-1].response if responses else {}) or {}
        task = st.get("task")
        slides: list[dict[str, Any]] = []
        if task:
            bullets = [b for b in [task.get("note")] if b]
            bullets += [f"Done: {t['title']}" for t in st.get("recent_tasks", []) if t.get("status") == "done"][:3]
            slides.append({"title": task["title"], "bullets": bullets or ["In progress"], "progress": task.get("progress")})
        else:
            done = [t for t in st.get("recent_tasks", []) if t.get("status") == "done"]
            slides.append({"title": f"{st.get('role', 'Update')}: status", "progress": None,
                           "bullets": ([f"Completed: {t['title']}" for t in done[:3]] or ["No active work right now"])})
        return [types.Part(text=json.dumps({"slides": slides}))]

    # ------------------------------------------------------------------ A2A peer question
    def _peer(self, text: str, calls: list[str], responses: list[Any], agent_id: str) -> list[types.Part]:
        if not calls:
            return [_fc("get_my_status")]
        st = (responses[-1].response if responses else {}) or {}
        q = text.split("over A2A:", 1)[-1].strip().splitlines()[0]
        task = st.get("task")
        mine = f" I'm currently working on '{task['title']}' ({task.get('progress', 0)}%)." if task else " I have capacity."
        return [types.Part(text=f"{st.get('name', agent_id)} ({st.get('role', '')}) here — re: “{q[:120]}”.{mine} I'll support with what my team owns.")]
