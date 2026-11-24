"""Handles events coming FROM the 3D UI (chat, summon, arrivals, approvals) and drives the agents accordingly."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from hq.agents.roster import AGENTS, ROOM_IDS
from hq.core.services import Services

log = logging.getLogger("hq.bridge")


class UIBridge:
    def __init__(self, svc: Services):
        self.svc = svc
        self._arrived: dict[tuple[str, str], asyncio.Event] = {}
        self._present_done: dict[str, asyncio.Event] = {}
        self._chat_locks: dict[str, asyncio.Lock] = {}
        self._tasks: set[asyncio.Task] = set()

    def _spawn(self, coro: Any, name: str) -> None:
        t = asyncio.create_task(coro, name=name)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)

    # ------------------------------------------------------------------ entry point
    def handle(self, ev: dict[str, Any]) -> None:
        kind = ev.get("type")
        w = self.svc.world
        try:
            if kind == "hello":
                log.info("UI connected: %d agents known to the UI", len(ev.get("agents", [])))
            elif kind == "arrived":
                a, r = ev.get("agent"), ev.get("room")
                if a in AGENTS and r in ROOM_IDS:
                    w.agents[a].room = None if r == AGENTS[a].dept else r
                    self._arrived.setdefault((a, r), asyncio.Event()).set()
            elif kind == "select":
                log.debug("UI selected %s", ev.get("agent"))
            elif kind == "chat":
                self._spawn(self.chat(ev.get("agent", ""), str(ev.get("text", ""))), "chat")
            elif kind == "summon":
                if str(ev.get("agenda", "")).strip():          # a real meeting: decks on the agenda, presentations, minutes
                    self._spawn(self.svc.workflows.start("meeting", {"room": ev.get("room", ""), "agenda": ev["agenda"],
                                                                     "attendees": list(ev.get("agents", []))}), "meeting")
                else:
                    self._spawn(self.summon(list(ev.get("agents", [])), ev.get("room", ""), ev.get("topic", "")), "summon")
            elif kind == "request_work":
                if ev.get("dept") and str(ev.get("text", "")).strip():
                    self._spawn(self.svc.workflows.start("work_request", {"dept": ev["dept"], "text": ev["text"], "agent": ev.get("agent")}), "request")
            elif kind == "room_message":
                if ev.get("room") in ROOM_IDS and str(ev.get("text", "")).strip():
                    self._spawn(self.svc.rooms.post(ev["room"], str(ev["text"])), "room")
            elif kind == "hand":
                if ev.get("action") == "now":
                    self.svc.rooms.priority(ev.get("room", ""), ev.get("agent", ""))
                elif ev.get("action") == "lower":
                    self.svc.rooms.lower(ev.get("room", ""), ev.get("agent", ""))
            elif kind == "town_now":
                self._spawn(self.svc.workflows.start("town_day", {"limit": int(ev.get("limit") or 4)}), "town")
            elif kind == "access_decision":
                res = self.svc.company.files.review_access(int(ev.get("id", 0)), "ceo", bool(ev.get("approve")), str(ev.get("note", "")) or "Decision by the CEO")
                if "error" in res:
                    w.log("⚠ " + res["error"])
                else:
                    w.access_changed()
            elif kind == "present_done":
                self._present_done.setdefault(ev.get("agent", ""), asyncio.Event()).set()
            elif kind == "approval":
                ok = self.svc.workflows.approve(ev.get("run", ""), bool(ev.get("approved", True)), str(ev.get("note", "")))
                if not ok:
                    w.log("⚠ That approval request is no longer open")
            elif kind == "clock":
                self._spawn(self.clock(ev), "clock")
            elif kind == "board_decision":
                res = self.svc.company.decide(str(ev.get("id", "")), "board", "approve" if ev.get("approved") else "reject", str(ev.get("note", "")) or "Board decision")
                if "error" in res:
                    w.log("⚠ " + res["error"])
                else:
                    w.biz_initiative(res)
            elif kind in ("state", "ping"):
                pass
            else:
                log.debug("ignored UI event %s", kind)
        except Exception:
            log.exception("bad UI event %s", ev)

    # ------------------------------------------------------------------ company clock controls from the dashboard
    async def clock(self, ev: dict[str, Any]) -> None:
        r = self.svc.runner
        act = ev.get("action")
        if act == "start":
            r.start(float(ev["seconds_per_day"]) if ev.get("seconds_per_day") is not None else None, ev.get("agents"))
        elif act == "pause":
            await r.pause()
        elif act == "step" and not r.running:
            await r.step(int(ev.get("days", 1)), ev.get("agents"))
        elif act == "config":
            if ev.get("seconds_per_day") is not None:
                r.seconds_per_day = max(0.0, float(ev["seconds_per_day"]))
            if ev.get("agents") is not None:
                r.agents = bool(ev["agents"])
            r._announce()

    # ------------------------------------------------------------------ chat with an agent
    async def chat(self, agent: str, text: str) -> None:
        w = self.svc.world
        if agent not in AGENTS or not text.strip():
            return
        lock = self._chat_locks.setdefault(agent, asyncio.Lock())
        w.convo("ceo", agent, "chat", text)
        async with lock:
            reply = await self.svc.runtime.chat(agent, text)
        w.chat_reply(agent, reply)
        w.convo(agent, "ceo", "chat", reply)

    # ------------------------------------------------------------------ "call these agents to a meeting and let them demo"
    async def summon(self, agents: list[str], room: str, topic: str) -> None:
        """The UI already walked the agents to the room. When they have all arrived, each one presents slides
        written by the agent itself (from its real task state); we wait for the UI to report each presentation done."""
        w = self.svc.world
        agents = [a for a in agents if a in AGENTS]
        if not agents or room not in ROOM_IDS:
            return
        for a in agents:
            self._arrived.pop((a, room), None)
            self._present_done.pop(a, None)
        w.meetings[room] = {"topic": topic, "members": agents}
        await asyncio.gather(*[self._wait(self._arrived, (a, room), 90) for a in agents])
        for a in agents:
            if room not in w.meetings:                      # meeting was ended meanwhile
                return
            slides = await self.svc.runtime.slides(a)
            w.present(a, slides)
            await self._wait(self._present_done, a, 20 + 10 * len(slides))
        w.log(f"Demo round finished in {room}")

    @staticmethod
    async def _wait(table: dict, key: Any, timeout: float) -> None:
        ev = table.setdefault(key, asyncio.Event())
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass
