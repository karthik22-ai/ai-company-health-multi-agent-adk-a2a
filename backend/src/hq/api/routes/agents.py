"""REST API. External agent runners, schedulers and dashboards use this; the 3D UI uses the WebSocket."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from hq.agents.roster import AGENTS, DEPARTMENTS, MEETING_ROOMS, ROOM_IDS, SHARED_ROOMS
from hq.core.services import Services


def svc_of(request: Request) -> Services:
    return request.app.state.svc


async def require_auth(request: Request) -> None:
    token = svc_of(request).settings.auth_token
    if not token:
        return
    if request.headers.get("authorization") == f"Bearer {token}" or request.query_params.get("token") == token:
        return
    raise HTTPException(401, "missing or invalid token")


router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


# ----------------------------------------------------------------------------- models
class TaskIn(BaseModel):
    title: str
    instructions: str = ""
    executor: Literal["adk", "external"] = "adk"       # external: an outside process reports progress itself
    wait: bool = False                                  # wait for the agent to finish before responding
    mock: dict[str, Any] | None = None                  # scripted behaviour for the offline mock LLM only


class ProgressIn(BaseModel):
    percent: int = Field(ge=0, le=100)
    note: str = ""
    status: Literal["doing", "blocked", "done", "failed"] | None = None


class StatusIn(BaseModel):
    state: Literal["idle", "working", "meeting", "blocked", "done", "error"]
    text: str | None = None


class TextIn(BaseModel):
    text: str


class MoveIn(BaseModel):
    room: str


class HandoffIn(BaseModel):
    from_agent: str = Field(alias="from")
    to: str
    item: str
    instructions: str = ""

    model_config = {"populate_by_name": True}


class ConsultIn(BaseModel):
    from_agent: str = Field(alias="from")
    to: str
    question: str

    model_config = {"populate_by_name": True}


class MeetingIn(BaseModel):
    room: str
    agents: list[str]
    topic: str = ""
    present: bool = False


class SystemIn(BaseModel):
    state: Literal["ok", "degraded", "down"]
    text: str = ""


class RunIn(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ApprovalIn(BaseModel):
    approved: bool = True
    note: str = ""


def _agent(agent_id: str) -> str:
    if agent_id not in AGENTS:
        raise HTTPException(404, f"unknown agent '{agent_id}'")
    return agent_id


def _room(room: str) -> str:
    if room not in ROOM_IDS:
        raise HTTPException(404, f"unknown room '{room}'")
    return room


# ----------------------------------------------------------------------------- state
@router.get("/state")
async def state(request: Request):
    s = svc_of(request)
    return {**s.world.snapshot(), "llm": s.settings.llm_label,
            "a2a_agents": len(s.cards)}


@router.get("/roster")
async def roster():
    return {
        "departments": [{"id": d.id, "name": d.name, "floor": d.floor, "lead": d.lead_name, "mission": d.mission,
                         "agents": [{"id": a.id, "name": a.name, "role": a.role, "lead": a.lead} for a in d.agents]}
                        for d in DEPARTMENTS.values()],
        "rooms": {**{k: v for k, v in SHARED_ROOMS.items()}, **{d.id: d.name for d in DEPARTMENTS.values()}},
        "meeting_rooms": MEETING_ROOMS,
    }


@router.get("/agents/{agent_id}")
async def agent(agent_id: str, request: Request):
    s = svc_of(request)
    a = s.world.agents[_agent(agent_id)]
    return {**a.model_dump(), "tasks": [t.model_dump() for t in s.world.tasks.values() if t.agent == agent_id]}


@router.get("/tasks")
async def tasks(request: Request, agent: str | None = None, status: str | None = None):
    ts = [t for t in svc_of(request).world.tasks.values() if (not agent or t.agent == agent) and (not status or t.status == status)]
    return [t.model_dump() for t in sorted(ts, key=lambda t: t.created, reverse=True)]


# ----------------------------------------------------------------------------- agent actions
@router.post("/agents/{agent_id}/tasks", status_code=202)
async def assign_task(agent_id: str, body: TaskIn, request: Request):
    """Give an agent work. executor=adk runs the Gemini agent; executor=external just records the task for an outside runner."""
    s = svc_of(request)
    w = s.world
    t = w.new_task(_agent(agent_id), body.title, body.instructions, source="api")
    if body.executor == "external":
        w.start_task(t)
        return t.model_dump()
    job = asyncio.create_task(s.runtime.run_task(t, mock=body.mock), name=f"task-{t.id}")
    if body.wait:
        await job
    return w.tasks[t.id].model_dump()


@router.post("/tasks/{task_id}/progress")
async def task_progress(task_id: str, body: ProgressIn, request: Request):
    """For external agent runners: report progress / completion / blockers for a task created with executor=external."""
    w = svc_of(request).world
    t = w.tasks.get(task_id)
    if not t:
        raise HTTPException(404, "unknown task")
    w.agents[t.agent].task_id = t.id
    if body.status == "done" or body.percent >= 100:
        w.finish_task(t, body.note)
    elif body.status == "blocked":
        w.block_task(t, body.note or "blocked")
    elif body.status == "failed":
        w.fail_task(t, body.note or "failed")
    else:
        w.update_progress(t.agent, body.percent, body.note)
        w.say(t.agent, f"{body.percent}% · {body.note}" if body.note else f"{body.percent}%", 2500)
    return w.tasks[t.id].model_dump()


@router.post("/agents/{agent_id}/status")
async def set_status(agent_id: str, body: StatusIn, request: Request):
    svc_of(request).world.set_status(_agent(agent_id), body.state, body.text)
    return {"ok": True}


@router.post("/agents/{agent_id}/say")
async def say(agent_id: str, body: TextIn, request: Request):
    svc_of(request).world.say(_agent(agent_id), body.text)
    return {"ok": True}


@router.post("/agents/{agent_id}/move")
async def move(agent_id: str, body: MoveIn, request: Request):
    svc_of(request).world.move(_agent(agent_id), _room(body.room))
    return {"ok": True}


@router.post("/agents/{agent_id}/desk")
async def desk(agent_id: str, request: Request):
    svc_of(request).world.desk(_agent(agent_id))
    return {"ok": True}


@router.post("/agents/{agent_id}/chat")
async def chat(agent_id: str, body: TextIn, request: Request):
    s = svc_of(request)
    reply = await s.runtime.chat(_agent(agent_id), body.text)
    s.world.chat_reply(agent_id, reply)
    return {"agent": agent_id, "reply": reply}


# ----------------------------------------------------------------------------- agent-to-agent
@router.post("/handoffs", status_code=202)
async def handoff(body: HandoffIn, request: Request):
    s = svc_of(request)
    t = await s.peers.hand_off(_agent(body.from_agent), _agent(body.to), body.item, body.instructions or body.item)
    return t.model_dump()


@router.post("/consult")
async def consult(body: ConsultIn, request: Request):
    s = svc_of(request)
    answer = await s.peers.ask(_agent(body.from_agent), _agent(body.to), body.question)
    return {"answer": answer}


@router.get("/a2a/messages")
async def a2a_messages(request: Request, limit: int = 100):
    return list(svc_of(request).peers.messages)[:limit]


@router.get("/a2a/agents")
async def a2a_agents(request: Request):
    s = svc_of(request)
    base = str(request.base_url).rstrip("/")
    return [{"id": i, "name": c.name, "description": c.description,
             "card_url": f"{base}/a2a/{i}/.well-known/agent-card.json",
             "skills": [sk.name for sk in c.skills]} for i, c in s.cards.items()]


# ----------------------------------------------------------------------------- meetings / systems / policy
@router.post("/meetings")
async def meeting(body: MeetingIn, request: Request):
    s = svc_of(request)
    room = _room(body.room)
    for a in body.agents:
        _agent(a)
    s.world.meeting(room, body.agents, body.topic)
    if body.present:
        s.world.log(f"Meeting in {room}: agents will present when you ask from the UI")
    return {"ok": True}


@router.post("/meetings/{room}/end")
async def end_meeting(room: str, request: Request):
    svc_of(request).world.end_meeting(_room(room))
    return {"ok": True}


@router.post("/systems/{name}")
async def system(name: str, body: SystemIn, request: Request):
    try:
        svc_of(request).world.set_system(name, body.state, body.text)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


@router.post("/policy")
async def policy(body: dict[str, Any], request: Request):
    w = svc_of(request).world
    w.auto_huddle = bool(body.get("auto_huddle", False))
    w.emit({"type": "policy", "autoHuddle": w.auto_huddle})
    return {"auto_huddle": w.auto_huddle}


@router.post("/commands")
async def raw_command(body: dict[str, Any], request: Request):
    """Escape hatch: send any UI command (see HQ-API.md) straight to the 3D UI."""
    if "type" not in body:
        raise HTTPException(422, "missing 'type'")
    svc_of(request).world.emit(body)
    return {"ok": True}


# ----------------------------------------------------------------------------- workflows
@router.get("/workflows")
async def workflows(request: Request):
    return svc_of(request).workflows.catalog()


@router.post("/workflows/{name}/runs", status_code=202)
async def start_workflow(name: str, body: RunIn, request: Request):
    try:
        run = await svc_of(request).workflows.start(name, body.params)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return run.model_dump()


@router.get("/workflows/runs")
async def runs(request: Request):
    return [r.model_dump() for r in svc_of(request).workflows.list()]


@router.get("/workflows/runs/{run_id}")
async def run(run_id: str, request: Request):
    r = svc_of(request).workflows.runs.get(run_id)
    if not r:
        raise HTTPException(404, "unknown run")
    return r.model_dump()


@router.post("/workflows/runs/{run_id}/approve")
async def approve(run_id: str, body: ApprovalIn, request: Request):
    if not svc_of(request).workflows.approve(run_id, body.approved, body.note):
        raise HTTPException(409, "run is not waiting for approval")
    return {"ok": True}


@router.post("/workflows/runs/{run_id}/cancel")
async def cancel(run_id: str, request: Request):
    if not await svc_of(request).workflows.cancel(run_id):
        raise HTTPException(409, "run is not active")
    return {"ok": True}


# ----------------------------------------------------------------------------- events
@router.get("/events/history")
async def history(request: Request, limit: int = 200):
    return svc_of(request).bus.event_log.tail(limit)


@router.get("/events")
async def events(request: Request):
    """Server-Sent Events stream of every command sent to the UI (the UI can also consume this with an http(s) URL)."""
    s = svc_of(request)
    q = s.bus.subscribe()

    async def gen():
        try:
            for c in s.world.resync_commands():
                yield {"data": json.dumps(c)}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    c = await asyncio.wait_for(q.get(), 15)
                except asyncio.TimeoutError:
                    yield {"comment": "keep-alive"}
                    continue
                yield {"data": json.dumps(c)}
        finally:
            s.bus.unsubscribe(q)

    return EventSourceResponse(gen())


@router.get("/factory")
async def factory(request: Request):
    """What the agent factory builds: the kinds of agents, how many, and every employee's toolset."""
    return svc_of(request).runtime.factory.describe()
