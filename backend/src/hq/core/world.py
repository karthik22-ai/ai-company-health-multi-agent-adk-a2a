"""The world model: what every agent is doing right now.

Every mutation goes through a method here, which (1) updates the model and (2) publishes the matching command
to the 3D UI over the event bus. Agents (ADK tools), LangGraph workflows and REST handlers all call these methods,
so the UI and the REST API can never disagree.
"""
from __future__ import annotations

import asyncio
import itertools
import time
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

from hq.agents.roster import AGENTS, DEPARTMENTS, ROOM_IDS, SYSTEMS, agent_name
from hq.core.bus import EventBus

TaskStatus = Literal["todo", "doing", "blocked", "done", "failed"]
AgentStateName = Literal["idle", "working", "meeting", "blocked", "done", "error"]


class Task(BaseModel):
    id: str
    agent: str
    title: str
    instructions: str = ""
    status: TaskStatus = "todo"
    progress: int | None = None
    note: str = ""
    result: str | None = None
    source: str = "api"                 # api | workflow:<name>/<run> | a2a:<from>
    created: float = Field(default_factory=time.time)
    updated: float = Field(default_factory=time.time)


class AgentState(BaseModel):
    id: str
    name: str
    role: str
    dept: str
    state: AgentStateName = "idle"
    text: str = "Idle"
    room: str | None = None             # None = at their own desk
    task_id: str | None = None


class SystemState(BaseModel):
    id: str
    name: str
    state: Literal["ok", "degraded", "down"] = "ok"
    text: str = ""


class World:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.agents: dict[str, AgentState] = {
            a.id: AgentState(id=a.id, name=a.name, role=a.role, dept=a.dept) for a in AGENTS.values()
        }
        self.tasks: dict[str, Task] = {}
        self.systems: dict[str, SystemState] = {k: SystemState(id=k, name=v) for k, v in SYSTEMS.items()}
        self.meeting_requests: list[dict[str, Any]] = []
        self.meetings: dict[str, dict[str, Any]] = {}      # room -> {topic, members}
        self.auto_huddle = False
        self.company: Any = None      # biz.company.Company, attached by build_services
        self.locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)   # one task at a time per agent
        self._ids = itertools.count(1)
        self.on_hire: list[Any] = []        # async hooks(spec): build the ADK agent, mount A2A
        self.on_access: list[Any] = []      # hooks(): e.g. start the Data team's access review

    # ------------------------------------------------------------------ helpers
    def _check_agent(self, agent: str) -> AgentState:
        if agent not in self.agents:
            raise KeyError(f"unknown agent '{agent}'")
        return self.agents[agent]

    def _check_room(self, room: str) -> str:
        if room not in ROOM_IDS:
            raise KeyError(f"unknown room '{room}'")
        return room

    def emit(self, cmd: dict[str, Any]) -> dict[str, Any]:
        self.bus.publish(cmd)
        return cmd

    # ------------------------------------------------------------------ status / speech / logs
    def set_status(self, agent: str, state: AgentStateName, text: str | None = None, *, now: bool = True) -> None:
        a = self._check_agent(agent)
        a.state = state
        a.text = text or {"idle": "Idle", "working": "Working", "meeting": "In a meeting", "blocked": "Blocked",
                          "done": "Done", "error": "Error"}[state]
        self.emit({"type": "status", "agent": agent, "state": state, "text": text, "now": now})

    def say(self, agent: str, text: str, ms: int = 3500) -> None:
        self._check_agent(agent)
        self.emit({"type": "say", "agent": agent, "text": text[:240], "ms": ms})
        self.room_log(self.room_of(agent), agent, "say", text)

    def log(self, text: str) -> None:
        self.emit({"type": "log", "text": text})

    def set_system(self, name: str, state: Literal["ok", "degraded", "down"], text: str = "") -> None:
        if name not in self.systems:
            raise KeyError(f"unknown system '{name}'")
        s = self.systems[name]
        s.state, s.text = state, text
        self.emit({"type": "system", "name": name, "state": state, "text": text})

    # ------------------------------------------------------------------ movement (only when explicitly requested)
    def move(self, agent: str, room: str, text: str | None = None) -> None:
        a = self._check_agent(agent)
        self._check_room(room)
        a.room = None if room == a.dept else room
        cmd: dict[str, Any] = {"type": "move", "agent": agent, "room": room}
        if text:
            cmd["text"] = text
        self.emit(cmd)

    def desk(self, agent: str) -> None:
        a = self._check_agent(agent)
        a.room = None
        self.emit({"type": "desk", "agent": agent})

    def meeting(self, room: str, agents: list[str], topic: str = "", *, meeting_id: str | None = None, agenda: str = "", organizer: str | None = None) -> None:
        self._check_room(room)
        for ag in agents:
            self._check_agent(ag)
            self.agents[ag].room = room
        self.meetings[room] = {"topic": topic, "members": list(agents), "id": meeting_id, "agenda": agenda or topic, "organizer": organizer}
        self.emit({"type": "meeting", "room": room, "agents": list(agents), "topic": topic})
        self.room_log(room, "system", "meeting", f"Meeting started: {agenda or topic} · " + ", ".join(agent_name(a) for a in agents), meeting_id)

    def end_meeting(self, room: str) -> None:
        if room in self.meetings:
            self.room_log(room, "system", "meeting", "Meeting ended")
        m = self.meetings.pop(room, None)
        for ag in (m["members"] if m else []):
            if ag in self.agents:
                self.agents[ag].room = None
        self.emit({"type": "end_meeting", "room": room})

    def present(self, agent: str, slides: list[dict[str, Any]], say: str | None = None) -> None:
        self._check_agent(agent)
        cmd: dict[str, Any] = {"type": "present", "agent": agent, "slides": slides}
        if say:
            cmd["say"] = say
        self.emit(cmd)
        room = self.room_of(agent)
        for s in slides:
            self.room_log(room, agent, "present", f"📊 {s.get('title', '')}: " + "; ".join(str(b) for b in (s.get("bullets") or [])[:4]))

    def handoff(self, src: str, dst: str, item: str, *, assign: bool = False) -> None:
        self._check_agent(src), self._check_agent(dst)
        self.emit({"type": "handoff", "from": src, "to": dst, "item": item, "assign": assign})

    def chat_reply(self, agent: str, text: str) -> None:
        self.room_log(self.room_of(agent), agent, "chat", text)
        self._check_agent(agent)
        self.emit({"type": "chat_reply", "agent": agent, "text": text})

    # ------------------------------------------------------------------ tasks
    def _push_task(self, t: Task) -> None:
        t.updated = time.time()
        self.emit({"type": "task", "agent": t.agent, "title": t.title, "progress": t.progress, "note": t.note,
                   "id": t.id, "status": t.status})

    def new_task(self, agent: str, title: str, instructions: str = "", source: str = "api") -> Task:
        self._check_agent(agent)
        t = Task(id=f"t{next(self._ids)}", agent=agent, title=title, instructions=instructions, source=source)
        self.tasks[t.id] = t
        self._push_task(t)
        return t

    def update_task(self, task: Task, *, status: TaskStatus | None = None, progress: int | None = None, note: str | None = None) -> None:
        """Update a board task WITHOUT changing the owner's visible state (used for long-running initiative implementation tasks)."""
        if status:
            task.status = status
        if progress is not None:
            task.progress = progress
        if note is not None:
            task.note = note
        self._push_task(task)

    def current_task(self, agent: str) -> Task | None:
        a = self._check_agent(agent)
        return self.tasks.get(a.task_id) if a.task_id else None

    def start_task(self, task: Task) -> None:
        task.status = "doing"
        task.progress = task.progress or 0
        self.agents[task.agent].task_id = task.id
        self._push_task(task)
        self.set_status(task.agent, "working", task.title)

    def update_progress(self, agent: str, percent: int, note: str = "") -> Task | None:
        t = self.current_task(agent)
        if not t:
            return None
        t.progress = max(0, min(100, int(percent)))
        if note:
            t.note = note
        if t.progress >= 100:
            t.status = "done"
        self._push_task(t)
        return t

    def block_task(self, task: Task, reason: str) -> None:
        task.status = "blocked"
        task.note = reason
        self._push_task(task)
        self.set_status(task.agent, "blocked", reason)

    def finish_task(self, task: Task, result: str = "") -> None:
        task.status = "done"
        task.progress = 100
        task.result = result or task.result
        self._push_task(task)
        a = self.agents[task.agent]
        if a.task_id == task.id:
            a.task_id = None
        self.set_status(task.agent, "done", f"Done: {task.title}")

    def fail_task(self, task: Task, error: str) -> None:
        task.status = "failed"
        task.note = error
        self._push_task(task)
        a = self.agents[task.agent]
        if a.task_id == task.id:
            a.task_id = None
        self.set_status(task.agent, "error", error[:120])

    # ------------------------------------------------------------------ business commands for the UI dashboard
    def biz_day(self, payload: dict[str, Any]) -> None:
        self.emit({"type": "biz_day", **payload})

    def biz_initiative(self, ini: dict[str, Any]) -> None:
        keep = {k: ini[k] for k in ("id", "title", "kind", "status", "proposer", "dept", "cost_est", "created", "decided", "start_date", "end_date",
                                    "rationale", "decision_note", "decided_by") if k in ini}
        keep["headline"] = ini.get("estimate", {}).get("headline", "")
        keep["compliance"] = ini.get("compliance", {})
        keep["reviews"] = ini.get("reviews", [])
        self.emit({"type": "initiative", "initiative": keep})

    def biz_note(self, note: dict[str, Any]) -> None:
        self.emit({"type": "note", "note": note})

    # ------------------------------------------------------------------ room records & conversations
    def room_of(self, agent: str) -> str:
        a = self.agents.get(agent)
        return (a.room or a.dept) if a else "lob"

    def room_log(self, room: str, speaker: str, kind: str, text: str, meeting: str | None = None) -> dict[str, Any] | None:
        """Everything said or done in a room: speech, meeting talk, enquiries, presentations, your messages."""
        if self.company is None or not text:
            return None
        if meeting is None and room in self.meetings:
            meeting = self.meetings[room].get("id")
        e = {"ts": time.time(), "sim_date": self.company.today.isoformat(), "room": room, "speaker": speaker, "kind": kind, "text": str(text)[:1200], "meeting": meeting}
        cur = self.company.store.db.execute("INSERT INTO room_log(ts,sim_date,room,speaker,kind,text,meeting) VALUES (?,?,?,?,?,?,?)",
                                            (e["ts"], e["sim_date"], room, speaker, kind, e["text"], meeting))
        self.company.store.commit()
        e["id"] = int(cur.lastrowid or 0)
        self.emit({"type": "room_log", "entry": e})
        return e

    def convo(self, frm: str, to: str, channel: str, text: str, room: str | None = None) -> None:
        """Who said what to whom: chats with you, A2A questions and hand-offs, customer enquiries, residents' messages, meetings."""
        if self.company is None or not text:
            return
        self.company.store.db.execute("INSERT INTO convos(ts,sim_date,frm,to_,channel,text,room) VALUES (?,?,?,?,?,?,?)",
                                      (time.time(), self.company.today.isoformat(), frm, to, channel, str(text)[:2000], room))
        self.company.store.commit()

    def remember(self, agent: str, kind: str, text: str, importance: float = 0.5) -> None:
        """Each agent (employee or resident) has its own long-term memory: what it did, said, decided and lived through."""
        if self.company is None or not text:
            return
        self.company.store.db.execute("INSERT INTO agent_memory(agent,ts,sim_date,kind,text,importance) VALUES (?,?,?,?,?,?)",
                                      (agent, time.time(), self.company.today.isoformat(), kind, str(text)[:600], float(importance)))
        self.company.store.commit()

    def memories(self, agent: str, query: str = "", limit: int = 8) -> list[dict[str, Any]]:
        """Recall: the most relevant memories (shared words + importance + recency), newest first."""
        if self.company is None:
            return []
        rows = self.company.store.rows("SELECT * FROM agent_memory WHERE agent=? ORDER BY id DESC LIMIT 400", (agent,))
        if not query:
            imp = sorted(rows[:120], key=lambda r: -(r["importance"] + (1 if r["kind"] == "life" else 0)))[:max(2, limit // 3)]
            out = rows[:limit - len(imp)] + [r for r in imp if r not in rows[:limit - len(imp)]]
            return sorted(out, key=lambda r: -r["id"])[:limit]
        words = {w for w in query.lower().split() if len(w) > 3}
        n = len(rows) or 1
        scored = sorted(rows, key=lambda r: -(len(words & set(r["text"].lower().split())) * 2 + r["importance"] + (n - rows.index(r)) / n))
        return sorted(scored[:limit], key=lambda r: -r["id"])

    def memory_block(self, agent: str, limit: int = 8, query: str = "") -> str:
        """Long-term summary (digest) + the memories most relevant to what they are doing now (or the most recent/important ones)."""
        m = [x for x in self.memories(agent, query=query, limit=limit) if x["kind"] != "digest"]
        dig = self.company.store.rows("SELECT * FROM agent_memory WHERE agent=? AND kind='digest' ORDER BY id DESC LIMIT 2", (agent,)) if self.company else []
        if not m and not dig:
            return ""
        out = ""
        if dig:
            out += "\nWhat you remember from earlier (summary):\n" + "\n".join(f"- {d['text']}" for d in reversed(dig))
        if m:
            out += "\nYour memories (most recent first; use them, stay consistent with them):\n" + "\n".join(f"- [{x['sim_date']}] {x['text']}" for x in m)
        return out

    def consolidate(self, agent: str, keep: int = 40, batch: int = 30) -> bool:
        """Nightly: once an agent has more than `keep` memories since its last digest, fold the oldest `batch` into one digest memory
        (the most important ones, kept short). No model call: cheap enough to run for every agent every day."""
        if self.company is None:
            return False
        st = self.company.store
        last = int(st.get_kv(f"digest:{agent}", 0) or 0)
        rows = st.rows("SELECT * FROM agent_memory WHERE agent=? AND id>? AND kind!='digest' ORDER BY id", (agent, last))
        if len(rows) <= keep:
            return False
        old = rows[:batch]
        top = sorted(old, key=lambda r: -r["importance"])[:6]
        text = f"{old[0]['sim_date']} to {old[-1]['sim_date']}: " + " | ".join(r["text"][:110] for r in sorted(top, key=lambda r: r["id"]))
        st.db.execute("INSERT INTO agent_memory(agent,ts,sim_date,kind,text,importance) VALUES (?,?,?,?,?,?)",
                      (agent, time.time(), self.company.today.isoformat(), "digest", text[:900], .75))
        st.set_kv(f"digest:{agent}", old[-1]["id"])
        st.commit()
        return True

    def threads(self, who: str) -> list[dict[str, Any]]:
        rows = self.company.store.rows(
            "SELECT CASE WHEN frm=? THEN to_ ELSE frm END AS other, channel, COUNT(*) n, MAX(ts) last_ts, MAX(sim_date) last_date, MIN(sim_date) first_date "
            "FROM convos WHERE frm=? OR to_=? GROUP BY other, channel ORDER BY last_ts DESC", (who, who, who))
        return rows

    def thread(self, who: str, other: str, limit: int = 200) -> list[dict[str, Any]]:
        return self.company.store.rows("SELECT * FROM (SELECT * FROM convos WHERE (frm=? AND to_=?) OR (frm=? AND to_=?) ORDER BY id DESC LIMIT ?) ORDER BY id",
                                       (who, other, other, who, limit))

    def usage(self, who: str) -> dict[str, Any]:
        rows = self.company.store.rows("SELECT day, prompt, output, calls FROM token_usage WHERE owner=? ORDER BY day", (who,))
        tot = {"prompt": sum(r["prompt"] for r in rows), "output": sum(r["output"] for r in rows), "calls": sum(r["calls"] for r in rows)}
        return {"total": tot | {"tokens": tot["prompt"] + tot["output"]}, "by_day": rows[-30:]}

    def room_history(self, room: str, limit: int = 120) -> list[dict[str, Any]]:
        if self.company is None:
            return []
        return self.company.store.rows("SELECT * FROM (SELECT * FROM room_log WHERE room=? ORDER BY id DESC LIMIT ?) ORDER BY id", (room, limit))

    # ------------------------------------------------------------------ work files, data access, hiring
    def work_file(self, meta: dict[str, Any]) -> None:
        self.emit({"type": "file", "file": meta})

    def access_changed(self) -> None:
        if self.company is not None:
            self.emit({"type": "access", **self.company.files.access_matrix()})
        for hook in self.on_access:
            hook()

    async def hire(self, name: str, role: str, dept: str, by: str, reason: str) -> Any:
        """People & Culture hires a new AI agent: roster + world + persistence, then the runtime/A2A hooks and the 3D desk."""
        from hq.agents.roster import add_agent
        spec = add_agent(name, role, dept)
        self.agents[spec.id] = AgentState(id=spec.id, name=spec.name, role=spec.role, dept=spec.dept)
        if self.company is not None:
            self.company.files.save_hire(spec, by, reason)
        for hook in self.on_hire:
            await hook(spec)
        self.emit({"type": "hire", "agent": {"id": spec.id, "name": spec.name, "role": spec.role, "dept": spec.dept, "hired_by": by, "reason": reason}})
        self.say(by, f"🤝 Hired {spec.name} as {spec.role}"[:130], 5000)
        self.log(f"{agent_name(by)} hired {spec.name} ({spec.role}) into {spec.dept}: {reason[:120]}")
        return spec

    # ------------------------------------------------------------------ snapshots
    def snapshot(self) -> dict[str, Any]:
        return {
            "agents": [a.model_dump() for a in self.agents.values()],
            "tasks": [t.model_dump() for t in self.tasks.values()],
            "systems": [s.model_dump() for s in self.systems.values()],
            "meetings": self.meetings,
            "meeting_requests": self.meeting_requests,
            "auto_huddle": self.auto_huddle,
            "departments": {d.id: {"name": d.name, "floor": d.floor, "lead": d.lead_name} for d in DEPARTMENTS.values()},
        }

    def resync_commands(self) -> list[dict[str, Any]]:
        """Commands that bring a freshly (re)loaded UI up to date with the current world."""
        cmds: list[dict[str, Any]] = [{"type": "policy", "autoHuddle": self.auto_huddle}]
        if self.company is not None:                 # hired agents first, so later commands can address them
            for h in self.company.files.hires():
                cmds.append({"type": "hire", "agent": {k: h[k] for k in ("id", "name", "role", "dept")}, "quiet": True})
        for s in self.systems.values():
            if s.state != "ok":
                cmds.append({"type": "system", "name": s.id, "state": s.state, "text": s.text})
        for t in self.tasks.values():
            cmds.append({"type": "task", "agent": t.agent, "title": t.title, "progress": t.progress, "note": t.note,
                         "id": t.id, "status": t.status})
        for a in self.agents.values():
            if a.state != "idle":
                cmds.append({"type": "status", "agent": a.id, "state": a.state, "text": a.text, "now": True})
            if a.room:
                cmds.append({"type": "move", "agent": a.id, "room": a.room})
        co = self.company
        if co is not None and co.store.last_date():
            cmds.append({"type": "biz_day", **co.dashboard_payload()})
            for ini in co.sim.initiatives.values():
                cmds.append({"type": "initiative", "initiative": co.public_initiative(ini)})
            for n in co.recent_notes(25)[::-1]:
                cmds.append({"type": "note", "note": n})
            for f in co.files.list(limit=120)[::-1]:
                cmds.append({"type": "file", "file": f, "quiet": True})
            cmds.append({"type": "access", **co.files.access_matrix()})
            for m in co.store.get_kv("meetings", [])[-30:]:
                cmds.append({"type": "meeting_done", **m, "files": co.files.list(meeting=m["meeting"], limit=20), "quiet": True})
        if co is not None:                           # the town exists from the first second, before any company day
            cmds.append({"type": "town", **co.town.snapshot()})
        cmds.append({"type": "resync_done"})
        return cmds

    def display(self, agent: str) -> str:
        return agent_name(agent)
