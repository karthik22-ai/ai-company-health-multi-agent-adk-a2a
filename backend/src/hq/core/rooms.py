"""Talking in a room: you post a message, people mentioned with @Name raise their hand and speak one at a time (a queue), so nobody talks over
anyone. Without a mention, the meeting's chair (or the department head in a department room) answers. Everything said is in the room record.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from hq.agents.roster import AGENTS, DEPARTMENTS, MEETING_ROOMS, dept_lead

log = logging.getLogger("hq.core.rooms")
MENTION = re.compile(r"@([A-Za-z][\w.\-']*(?:\s+[A-Z][\w'\-]+)?)")


class RoomTalk:
    def __init__(self, svc: Any):
        self.svc = svc
        self.queues: dict[str, list[str]] = {}
        self.workers: dict[str, asyncio.Task] = {}
        self.last_ask: dict[str, str] = {}

    # ------------------------------------------------------------------ who is meant
    def resolve(self, token: str, room: str) -> str | None:
        t = token.strip().lower()
        if t in AGENTS:
            return t
        here = set(self.people_in(room))
        full = [a.id for a in AGENTS.values() if a.name.lower() == t]
        if full:
            return full[0]
        first = [a.id for a in AGENTS.values() if a.name.split()[0].lower() == t.split()[0]]
        if not first:
            return None
        return next((a for a in first if a in here), first[0])

    def people_in(self, room: str) -> list[str]:
        w = self.svc.world
        if room in w.meetings:
            return list(w.meetings[room].get("members", []))
        if room in DEPARTMENTS:
            return [a.id for a in DEPARTMENTS[room].agents]
        return [a for a, s in w.agents.items() if s.room == room]

    def chair(self, room: str) -> str | None:
        w = self.svc.world
        if room in w.meetings:
            m = w.meetings[room]
            return m.get("organizer") or (m.get("members") or [None])[0]
        if room in DEPARTMENTS:
            return dept_lead(room).id
        ppl = self.people_in(room)
        return ppl[0] if ppl else None

    # ------------------------------------------------------------------ API
    async def post(self, room: str, text: str) -> dict[str, Any]:
        w = self.svc.world
        text = text.strip()[:800]
        if not text:
            return {"error": "empty message"}
        w.room_log(room, "ceo", "user", text)
        self.last_ask[room] = text
        self.asker = getattr(self, "asker", {})
        ids = [i for i in (self.resolve(m, room) for m in MENTION.findall(text)) if i]
        if not ids:
            c = self.chair(room)
            ids = [c] if c else []
        for a in dict.fromkeys(ids):
            w.convo("ceo", a, "meeting", text, room)
            self.raise_hand(room, a)
        if room not in self.workers or self.workers[room].done():
            self.workers[room] = asyncio.create_task(self._work(room), name=f"room-{room}")
        return {"ok": True, "queue": self.queues.get(room, [])}

    def raise_hand(self, room: str, agent: str) -> None:
        w = self.svc.world
        q = self.queues.setdefault(room, [])
        if agent in q:
            return
        q.append(agent)
        if room in MEETING_ROOMS and room in w.meetings and agent not in w.meetings[room]["members"]:
            w.meetings[room]["members"].append(agent)        # someone mentioned from outside walks in
            w.move(agent, room, "Called into the meeting")
        w.emit({"type": "hand", "room": room, "agent": agent, "raised": True, "queue": list(q)})
        w.emit({"type": "say", "agent": agent, "text": "✋", "ms": 2500})

    def priority(self, room: str, agent: str) -> None:
        q = self.queues.get(room, [])
        if agent in q and len(q) > 1:
            q.remove(agent)
            q.insert(1 if self._speaking(room) else 0, agent)
            self.svc.world.emit({"type": "hand", "room": room, "agent": agent, "raised": True, "queue": list(q)})

    def lower(self, room: str, agent: str) -> None:
        q = self.queues.get(room, [])
        if agent in q and not (self._speaking(room) and q[0] == agent):
            q.remove(agent)
            self.svc.world.emit({"type": "hand", "room": room, "agent": agent, "raised": False, "queue": list(q)})

    def _speaking(self, room: str) -> bool:
        t = self.workers.get(room)
        return bool(t and not t.done())

    # ------------------------------------------------------------------ one speaker at a time
    async def _work(self, room: str) -> None:
        w, rt = self.svc.world, self.svc.runtime
        q = self.queues.setdefault(room, [])
        chained = 0
        while q:
            a = q[0]
            w.emit({"type": "speaking", "room": room, "agent": a, "queue": list(q)})
            hist = w.room_history(room, 14)
            transcript = "\n".join(f"{'CEO' if e['speaker'] == 'ceo' else (AGENTS[e['speaker']].name if e['speaker'] in AGENTS else e['speaker'])}: {e['text'][:300]}"
                                   for e in hist if e["kind"] in ("user", "speech", "say", "present", "chat"))
            agenda = (w.meetings.get(room) or {}).get("agenda") or (w.meetings.get(room) or {}).get("topic", "")
            ans = await rt.meeting_reply(a, room, agenda, transcript, self.last_ask.get(room, ""))
            w.emit({"type": "say", "agent": a, "text": ans[:240], "ms": min(12000, 2500 + 45 * len(ans))})
            w.room_log(room, a, "speech", ans)
            w.convo(a, "ceo", "meeting", ans, room)
            w.remember(a, "meeting", f"In {room} the CEO asked \"{self.last_ask.get(room, '')[:120]}\"; I said: {ans[:200]}", 0.6)
            q.pop(0)
            w.emit({"type": "hand", "room": room, "agent": a, "raised": False, "queue": list(q)})
            await asyncio.sleep(max(0.0, self.svc.settings.step_delay) * 2)
            if chained < 3:                                       # "@Name, can you take that?" passes the floor on
                for m in MENTION.findall(ans):
                    nxt = self.resolve(m, room)
                    if nxt and nxt != a and nxt not in q:
                        self.raise_hand(room, nxt)
                        chained += 1
        w.emit({"type": "speaking", "room": room, "agent": None, "queue": []})
