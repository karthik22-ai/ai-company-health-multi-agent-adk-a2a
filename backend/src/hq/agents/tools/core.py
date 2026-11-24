"""The tools every ADK agent can call. They are the ONLY way an agent affects the world (and therefore the 3D UI).

Tools are created per agent (closures), so an agent can only ever act as itself.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from hq.agents.roster import AGENTS, MEETING_ROOMS, SYSTEMS
from hq.core.config import Settings
from hq.core.world import World

log = logging.getLogger("hq.tools")
VALID_STATES = {"working", "idle", "blocked", "done", "error"}


def make_tools(agent_id: str, world: World, peers: Any, settings: Settings, *, chat: bool = False) -> list[Callable]:
    me = AGENTS[agent_id]

    async def get_my_status() -> dict:
        """Return your current state, active task and recently finished work. Use it before reporting facts about yourself."""
        a = world.agents[agent_id]
        t = world.current_task(agent_id)
        recent = [x for x in world.tasks.values() if x.agent == agent_id and x.id != (t.id if t else None)]
        recent.sort(key=lambda x: x.updated, reverse=True)
        return {
            "agent_id": agent_id, "name": me.name, "role": me.role, "state": a.state, "text": a.text,
            "task": ({"title": t.title, "progress": t.progress, "note": t.note, "status": t.status} if t else None),
            "recent_tasks": [{"title": x.title, "status": x.status, "progress": x.progress, "result": (x.result or "")[:200]} for x in recent[:5]],
        }

    async def set_status(state: str, text: str) -> dict:
        """Set your visible status. state must be one of: working, idle, blocked, done, error. text is a short description (e.g. what you are doing)."""
        if state not in VALID_STATES:
            return {"error": f"state must be one of {sorted(VALID_STATES)}"}
        t = world.current_task(agent_id)
        if state == "done" and t:
            world.finish_task(t, t.result or "")
        elif state == "blocked" and t:
            world.block_task(t, text)
        else:
            world.set_status(agent_id, state, text)  # type: ignore[arg-type]
        return {"ok": True, "state": state}

    async def update_progress(percent: int, note: str = "") -> dict:
        """Report progress on your active task. percent is 0-100; note is one short sentence about what was just achieved."""
        t = world.update_progress(agent_id, percent, note)
        if not t:
            return {"error": "you have no active task"}
        world.say(agent_id, f"{t.progress}% · {note}" if note else f"{t.progress}%", 2500)
        return {"ok": True, "progress": t.progress}

    async def report_blocker(reason: str) -> dict:
        """Declare that you cannot continue and say why (what is missing or failing). Your teammates will see you as blocked."""
        t = world.current_task(agent_id)
        if t:
            world.block_task(t, reason)
        else:
            world.set_status(agent_id, "blocked", reason)
        world.say(agent_id, f"Blocked: {reason}", 5000)
        if world.auto_huddle:
            world.log(f"{me.name} is blocked – huddle policy is on")
        return {"ok": True, "blocked": True}

    async def consult_peer(peer_id: str, question: str) -> dict:
        """Ask a colleague a question over the A2A protocol and wait for their answer. peer_id is the colleague's agent id, e.g. 'data.arjun'."""
        if peer_id not in AGENTS or peer_id == agent_id:
            return {"error": f"unknown colleague '{peer_id}'"}
        answer = await peers.ask(agent_id, peer_id, question)
        return {"peer": peer_id, "answer": answer}

    async def hand_off_work(peer_id: str, item: str, instructions: str) -> dict:
        """Pass a piece of work to a colleague over the A2A protocol. item is a short name for the deliverable; instructions say exactly what to do."""
        if peer_id not in AGENTS or peer_id == agent_id:
            return {"error": f"unknown colleague '{peer_id}'"}
        task = await peers.hand_off(agent_id, peer_id, item, instructions)
        return {"status": "handed_off", "peer": peer_id, "task_id": task.id}

    async def lookup_system(name: str) -> dict:
        """Check the health of a finance system. name is one of: policy, claims, crm, dw, web, pay."""
        s = world.systems.get(name)
        if not s:
            return {"error": f"unknown system, choose from {sorted(SYSTEMS)}"}
        return {"system": s.name, "state": s.state, "detail": s.text}

    async def request_meeting(topic: str, attendee_ids: list[str]) -> dict:
        """Ask for a short meeting with specific colleagues, only if a blocker truly needs a conversation. It happens only if the CFO's office allows it."""
        who = [a for a in attendee_ids if a in AGENTS]
        req = {"from": agent_id, "topic": topic, "attendees": who}
        world.meeting_requests.append(req)
        world.log(f"{me.name} requested a meeting: {topic}")
        if settings.auto_meetings or world.auto_huddle:
            room = next((r for r in ["mr1", "mr2", "mr3"] if r not in world.meetings), "brd")
            world.meeting(room, [agent_id, *who], topic)
            return {"status": "scheduled", "room": room}
        return {"status": "pending_approval"}

    async def recall_memories(query: str = "") -> list:
        """Search your own long-term memory (things you did, decided, were told). query: words to look for; empty = most recent."""
        return [{"date": m["sim_date"], "kind": m["kind"], "memory": m["text"]} for m in world.memories(agent_id, query, 10)]

    async def remember(note: str, importance: float = 0.5) -> dict:
        """Save something worth remembering later (a commitment, a lesson, a fact about a colleague or customer). importance 0-1."""
        world.remember(agent_id, "note", note, max(0.0, min(1.0, float(importance))))
        return {"ok": True}

    tools: list[Callable] = [get_my_status, set_status, update_progress, report_blocker, consult_peer, hand_off_work,
                             lookup_system, request_meeting, recall_memories, remember]


    if chat:
        async def go_to_room(room_id: str) -> dict:
            """Walk to a room, ONLY because the user asked you to come to a meeting or show your work. room_id: mr1, mr2, mr3 or brd."""
            if room_id not in MEETING_ROOMS:
                return {"error": f"room_id must be one of {MEETING_ROOMS}"}
            world.meeting(room_id, [agent_id], "Meeting with you")
            world.set_status(agent_id, "meeting", f"In {room_id}")
            return {"ok": True, "message": f"On my way to {room_id}."}

        async def return_to_desk() -> dict:
            """Go back to your own desk, ONLY because the user asked you to."""
            if world.agents[agent_id].state == "meeting":
                world.set_status(agent_id, "idle", "Back at desk")
            world.desk(agent_id)
            return {"ok": True}

        tools += [go_to_room, return_to_desk]
    return tools
