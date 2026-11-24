"""REST API for the synthetic company: data, decisions, the clock."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from hq.api.routes.agents import require_auth, svc_of

router = APIRouter(prefix="/api/company", dependencies=[Depends(require_auth)])


def co(request: Request):
    return svc_of(request).company


class ClockIn(BaseModel):
    action: Literal["start", "pause", "step"]
    days: int = Field(default=1, ge=1, le=400)
    seconds_per_day: float | None = Field(default=None, ge=0, le=3600)
    agents: bool | None = None


class QueryIn(BaseModel):
    sql: str


class ProposalIn(BaseModel):
    kind: str
    title: str
    rationale: str = ""
    params: dict[str, Any] = Field(default_factory=dict)


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = ""


@router.get("/snapshot")
async def snapshot(request: Request):
    return co(request).dashboard_payload()


@router.get("/kpis")
async def kpis(request: Request, window_days: int = 7):
    return co(request).kpi_window(max(1, min(window_days, 365)))


@router.get("/series")
async def series(request: Request, metric: str, days: int = 60):
    out = co(request).series(metric, max(1, min(days, 400)))
    if not out:
        raise HTTPException(404, f"unknown metric '{metric}'")
    return out


@router.get("/breakdown")
async def breakdown(request: Request, metric: str = "sales", by: str = "channel", days: int = 28):
    return co(request).breakdown(by, days, metric)


@router.get("/forecast")
async def forecast(request: Request, metric: str = "new_sales", days: int = 7):
    return co(request).forecast(metric, days)


@router.get("/products")
async def products(request: Request):
    return co(request).products_view()


@router.get("/team")
async def team(request: Request):
    return co(request).team_status()


@router.get("/alerts")
async def alerts(request: Request):
    return co(request).alerts()


@router.get("/events")
async def events(request: Request, limit: int = 30):
    return co(request).store.rows("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))


@router.get("/notes")
async def notes(request: Request, limit: int = 30, kind: str | None = None):
    return co(request).recent_notes(limit, kind)


@router.get("/initiatives")
async def initiatives(request: Request, status: str | None = None):
    c = co(request)
    return [c.public_initiative(i) for i in c.list_initiatives(status)]


@router.post("/proposals", status_code=201)
async def propose(body: ProposalIn, request: Request):
    """The board (you) can propose an initiative too; the agents review and decide it like any other."""
    s = svc_of(request)
    ini = s.company.propose("board", "exec", body.kind, body.title, body.rationale, body.params)
    if "error" in ini:
        raise HTTPException(422, ini["error"])
    s.world.biz_initiative(ini)
    return s.company.public_initiative(ini)


@router.post("/initiatives/{ini_id}/decide")
async def decide(ini_id: str, body: DecisionIn, request: Request):
    """Board override: approve or reject an initiative yourself."""
    s = svc_of(request)
    res = s.company.decide(ini_id, "board", body.decision, body.note or "Board decision")
    if "error" in res:
        raise HTTPException(409, res["error"])
    s.world.biz_initiative(res)
    return s.company.public_initiative(res)


@router.post("/query")
async def query(body: QueryIn, request: Request):
    return co(request).store.query_readonly(body.sql)


@router.get("/clock")
async def clock_state(request: Request):
    return svc_of(request).runner.state()


@router.post("/clock")
async def clock(body: ClockIn, request: Request):
    r = svc_of(request).runner
    if body.action == "start":
        r.start(body.seconds_per_day, body.agents)
    elif body.action == "pause":
        await r.pause()
    else:
        if r.running:
            raise HTTPException(409, "pause the clock before stepping manually")
        if body.seconds_per_day is not None:
            r.seconds_per_day = body.seconds_per_day
        await r.step(body.days, body.agents)
    return r.state()


@router.get("/profile")
async def profile(request: Request):
    """Company details: who we are, people, health care, plans, market position, offers, budget."""
    return co(request).profile()


@router.get("/sales")
async def sales(request: Request, recent: int = 25):
    """Memberships sold and lost: counts (today, 7 and 28 days, all time) and the latest sales with who, plan, price, previous fund and why."""
    return co(request).sales(min(max(recent, 1), 200))
