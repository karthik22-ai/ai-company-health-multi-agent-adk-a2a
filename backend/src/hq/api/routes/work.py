"""REST API for the teams' work: files (view + download), data access, hires, meetings and requests."""
from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from hq.agents.roster import AGENTS, DEPARTMENTS, MEETING_ROOMS
from hq.api.routes.agents import require_auth, svc_of
from hq.work import render

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def files_of(request: Request):
    return svc_of(request).company.files


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:80] or "file"


@router.get("/files")
async def list_files(request: Request, dept: str | None = None, author: str | None = None, kind: str | None = None, meeting: str | None = None,
                     limit: int = 100):
    L = files_of(request).list(dept=dept, author=author, kind=kind, meeting=meeting, limit=min(limit, 300))
    checks = request.app.state.svc.company.guard.all()
    return [f | {"check": {"ok": checks[f["id"]]["ok"], "checked": checks[f["id"]]["checked"]} if f["id"] in checks else None} for f in L]


@router.get("/files/{fid}")
async def get_file(request: Request, fid: str):
    f = files_of(request).get(fid)
    if not f:
        raise HTTPException(404, "no such file")
    return f | {"check": request.app.state.svc.company.guard.get(fid)}


@router.get("/files/{fid}/view")
async def view_file(request: Request, fid: str):
    """The file as a page (dashboards, reports, decks, apps). Apps are served with a strict sandbox CSP."""
    f = files_of(request).get(fid)
    if not f:
        raise HTTPException(404, "no such file")
    headers = {"Content-Security-Policy": "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:"} \
        if f["kind"] == "app" else {}
    return HTMLResponse(render.to_html(f), headers=headers)


@router.get("/files/{fid}/download")
async def download_file(request: Request, fid: str, fmt: Literal["html", "md", "csv", "pptx", "json"] = "html"):
    f = files_of(request).get(fid)
    if not f:
        raise HTTPException(404, "no such file")
    base = f"{f['id']}_{_safe(f['title'])}"
    if fmt == "pptx":
        data = render.to_pptx(f)
        if data is None:
            raise HTTPException(501, "PowerPoint export needs python-pptx on the server")
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        headers={"Content-Disposition": f'attachment; filename="{base}.pptx"'})
    if fmt == "md":
        return PlainTextResponse(render.to_markdown(f), headers={"Content-Disposition": f'attachment; filename="{base}.md"'})
    if fmt == "csv":
        return PlainTextResponse(render.to_csv(f), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{base}.csv"'})
    if fmt == "json":
        import json
        return Response(json.dumps(f, default=str, indent=2), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{base}.json"'})
    return HTMLResponse(render.to_html(f), headers={"Content-Disposition": f'attachment; filename="{base}.html"'})


@router.get("/access")
async def access(request: Request):
    return files_of(request).access_matrix()


@router.get("/access/{agent_id}")
async def access_for(request: Request, agent_id: str):
    if agent_id not in AGENTS:
        raise HTTPException(404, "unknown agent")
    return files_of(request).datasets_for(agent_id)


class AccessDecision(BaseModel):
    approve: bool
    note: str = "Decision by the CEO"


@router.post("/access/requests/{rid}")
async def decide_access(request: Request, rid: int, body: AccessDecision):
    s = svc_of(request)
    res = s.company.files.review_access(rid, "ceo", body.approve, body.note)
    if "error" in res:
        raise HTTPException(400, res["error"])
    s.world.access_changed()
    return res


@router.get("/hires")
async def hires(request: Request):
    return files_of(request).hires()


@router.get("/app-requests")
async def app_requests(request: Request):
    """IT's app backlog: requests from teams, from the company's numbers and from the CEO, and what was delivered."""
    ar = svc_of(request).company.app_requests
    return {"counts": ar.counts(), "requests": ar.list(None, 100)}


class MeetingIn(BaseModel):
    room: str = "mr1"
    agenda: str = Field(min_length=3, max_length=600)
    attendees: list[str] = Field(min_length=1, max_length=8)


@router.post("/meetings/agenda")
async def start_meeting(request: Request, body: MeetingIn):
    s = svc_of(request)
    bad = [a for a in body.attendees if a not in AGENTS]
    if bad or body.room not in MEETING_ROOMS:
        raise HTTPException(400, f"unknown attendees {bad} or room (rooms: {MEETING_ROOMS})")
    run = await s.workflows.start("meeting", {"room": body.room, "agenda": body.agenda, "attendees": body.attendees})
    return {"run": run.id, "meeting": f"M-{run.id}"}


class RequestIn(BaseModel):
    dept: str
    text: str = Field(min_length=3, max_length=800)
    agent: str | None = None


@router.post("/requests")
async def work_request(request: Request, body: RequestIn):
    s = svc_of(request)
    if body.dept not in DEPARTMENTS:
        raise HTTPException(400, "unknown department")
    run = await s.workflows.start("work_request", body.model_dump())
    return {"run": run.id}


# ----------------------------------------------------------------------------- the town and the rooms
@router.get("/town")
async def town(request: Request):
    return svc_of(request).company.town.snapshot()


@router.get("/town/insights")
async def town_insights(request: Request):
    return svc_of(request).company.town.insights()


@router.get("/town/residents/{rid}")
async def town_resident(request: Request, rid: str):
    h = svc_of(request).company.town.history(rid)
    if not h:
        raise HTTPException(404, "no such resident")
    return h


class TownRun(BaseModel):
    limit: int = Field(default=4, ge=1, le=20)
    residents: list[str] | None = None
    reason: str | None = None


@router.post("/town/run")
async def town_run(request: Request, body: TownRun):
    run = await svc_of(request).workflows.start("town_day", body.model_dump(exclude_none=True))
    return {"run": run.id}


@router.get("/rooms/{room}/log")
async def room_log(request: Request, room: str, limit: int = 150):
    return svc_of(request).world.room_history(room, min(limit, 500))


class RoomMsg(BaseModel):
    text: str = Field(min_length=1, max_length=800)


@router.post("/rooms/{room}/message")
async def room_message(request: Request, room: str, body: RoomMsg):
    return await svc_of(request).rooms.post(room, body.text)


# ----------------------------------------------------------------------------- people: conversations and token usage (employees and residents)
@router.get("/people/{who}/threads")
async def threads(request: Request, who: str):
    s = svc_of(request)
    town = s.company.town
    out = []
    for t in s.world.threads(who):
        o = t["other"]
        if o == "ceo":
            t["name"], t["kind"] = "You (CEO)", "ceo"
        elif o in AGENTS:
            t["name"], t["kind"], t["role"] = AGENTS[o].name, "employee", AGENTS[o].role
        else:
            r = town.resident(o)
            t["name"], t["kind"], t["role"] = (r["name"] if r else o), "resident", (r.get("occupation") if r else "")
        out.append(t)
    return out


@router.get("/people/{who}/thread")
async def thread(request: Request, who: str, other: str):
    return svc_of(request).world.thread(who, other)


@router.get("/people/{who}/usage")
async def usage(request: Request, who: str):
    return svc_of(request).world.usage(who)


class TalkIn(BaseModel):
    text: str = Field(min_length=1, max_length=800)


@router.post("/people/{who}/talk")
async def talk(request: Request, who: str, body: TalkIn):
    """Talk to anyone: an employee or a town resident. Returns their reply."""
    s = svc_of(request)
    if who not in AGENTS and not s.company.town.resident(who):
        raise HTTPException(404, "unknown person")
    return {"reply": await s.runtime.talk(who, body.text)}


@router.get("/people/{who}/memory")
async def memory(request: Request, who: str, q: str = "", limit: int = 30):
    return svc_of(request).world.memories(who, q, min(limit, 200))
