"""REST API for agent quality and observability: traces, ops, evaluations, weekly goals and the company timeline."""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from hq.api.routes.agents import require_auth, svc_of
from hq.quality import traces

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])
# Indicative Gemini prices in USD per million tokens; set HQ_PRICE_IN_PER_M / HQ_PRICE_OUT_PER_M to your actual Vertex AI prices.
PRICE_IN = float(os.environ.get("HQ_PRICE_IN_PER_M", "0.30"))
PRICE_OUT = float(os.environ.get("HQ_PRICE_OUT_PER_M", "2.50"))


def _evals(request: Request):
    svc = svc_of(request)
    if getattr(svc, "evals", None) is None:
        from hq.quality.evals import Evals
        svc.evals = Evals(svc)
    return svc.evals


# ------------------------------------------------------------------ tracing
@router.get("/traces")
async def list_traces(request: Request, agent: str | None = None, status: str | None = None, limit: int = 100):
    """Recent agent runs: who, what kind (task, chat, town, …), tools used, model calls, tokens, time and outcome."""
    return traces.list_traces(svc_of(request).company.store, agent, status, min(max(limit, 1), 500))


@router.get("/traces/{tid}")
async def get_trace(request: Request, tid: int):
    """One run in full: the prompt, every tool call with its arguments and result, and the reply."""
    t = traces.get_trace(svc_of(request).company.store, tid)
    if not t:
        raise HTTPException(404, "no such trace")
    return t


# ------------------------------------------------------------------ operations
@router.get("/ops")
async def ops(request: Request):
    """Live operations: model call rate, quota errors, queue, tokens and estimated cost, errors by kind of work."""
    from hq.llm import guarded
    svc = svc_of(request)
    st = svc.company.store
    day = st.rows("SELECT SUM(prompt) p, SUM(output) o, SUM(calls) c FROM token_usage WHERE day=?", (time.strftime("%Y-%m-%d"),))
    d = day[0] if day else {}
    p, o = d.get("p") or 0, d.get("o") or 0
    return {"llm": svc.settings.llm_label, "gate": guarded.stats(), "last_10min": traces.summary(st, 10), "last_60min": traces.summary(st, 60),
            "today": {"prompt_tokens": p, "output_tokens": o, "model_calls": d.get("c") or 0,
                      "cost_usd_estimate": round(p / 1e6 * PRICE_IN + o / 1e6 * PRICE_OUT, 2), "prices_per_m": [PRICE_IN, PRICE_OUT]},
            "clock": svc.runner.state() if svc.runner else None,
            "workflows": [{"id": r.id, "name": r.name, "status": r.status, "started": r.started} for r in list(svc.workflows.runs.values())[-15:]]}


# ------------------------------------------------------------------ evaluations
@router.get("/evals")
async def eval_history(request: Request, n: int = 10):
    from hq.quality.evals import CASES
    e = _evals(request)
    return {"running": e.running, "cases": [{"id": c["id"], "agent": c["agent"], "kind": c["kind"], "question": c["question"]} for c in CASES],
            "runs": e.history(min(n, 50))}


@router.post("/evals/run")
async def eval_run(request: Request, wait: bool = False):
    """Ask agents the evaluation questions and score them against the data. Runs in the background unless wait=true."""
    e, svc = _evals(request), svc_of(request)
    if e.running:
        raise HTTPException(409, "an evaluation is already running")

    def progress(res: dict) -> None:
        svc.world.emit({"type": "eval_case", "result": res})

    async def go() -> dict:
        out = await e.run(on_case=progress)
        svc.world.emit({"type": "eval_done", "score": out["score"], "passed": out["passed"], "total": out["total"]})
        svc.world.log(f"🧪 Evaluation: {out['passed']}/{out['total']} passed")
        return out
    if wait:
        return await go()
    asyncio.create_task(go())
    return {"started": True}


# ------------------------------------------------------------------ goals
@router.get("/goals")
async def goals(request: Request):
    co = svc_of(request).company
    return {"this_week": co.goals.for_week(), "reviews": co.goals.reviews(8)}


# ------------------------------------------------------------------ timeline (replay a period day by day)
@router.get("/timeline")
async def timeline(request: Request, days: int = 28):
    """Day by day: the KPIs and what happened (sales, losses, campaigns, initiatives, documents, competitor moves, life events, goal reviews)."""
    co = svc_of(request).company
    st = co.store
    rows = st.rows("SELECT * FROM (SELECT * FROM daily_kpi ORDER BY date DESC LIMIT ?) ORDER BY date", (min(max(days, 1), 120),))
    if not rows:
        return {"days": []}
    a, b = rows[0]["date"], rows[-1]["date"]
    ev = st.rows("SELECT date, kind, insurer, text, data FROM town_events WHERE date>=? AND date<=? AND kind IN "
                 "('buy','switch','birth','death','move_in','partner','complaint','word_of_mouth','competitor','facility') ORDER BY id", (a, b))
    camps = st.rows("SELECT date, title, by_agent FROM town_campaigns WHERE date>=? AND date<=?", (a, b))
    files = st.rows("SELECT sim_date, id, kind, title, author FROM files WHERE sim_date>=? AND sim_date<=?", (a, b))
    inis = [i for i in co.sim.initiatives.values() if i.get("start_date") and a <= i["start_date"] <= b]
    revs = {r["to"]: r for r in co.goals.reviews(20)}
    out = []
    for k in rows:
        d = k["date"]
        happen = []
        for e in ev:
            if e["date"] != d:
                continue
            data = json.loads(e["data"] or "{}")
            if e["kind"] in ("buy", "switch"):
                if e["insurer"] == "aich":
                    happen.append({"icon": "🧾", "text": e["text"][:160], "tone": "good"})
                elif data.get("before_insurer") == "aich":
                    happen.append({"icon": "👋", "text": e["text"][:160], "tone": "bad"})
            else:
                happen.append({"icon": {"birth": "👶", "death": "🕯️", "move_in": "🏠", "partner": "💞", "complaint": "⚠️", "word_of_mouth": "💬",
                                        "competitor": "🏁", "facility": "🏗️"}.get(e["kind"], "•"), "text": e["text"][:160],
                               "tone": "bad" if e["kind"] == "complaint" else ""})
        happen += [{"icon": "📣", "text": f"Campaign: {c['title']}", "tone": "good"} for c in camps if c["date"] == d]
        happen += [{"icon": "🚀", "text": f"Initiative started: {i['id']} {i['title']}", "tone": "good"} for i in inis if i["start_date"] == d]
        happen += [{"icon": "📄", "text": f"{f['kind'].title()}: {f['title']}", "file": f["id"]} for f in files if f["sim_date"] == d]
        if d in revs:
            happen.append({"icon": "🎯", "text": co.goals.lesson(revs[d])[:200]})
        out.append({"date": d, "kpi": {x: k[x] for x in ("policies_in_force", "new_sales", "cancellations", "premium_revenue", "claims_incurred",
                                                          "loss_ratio", "claims_sla_pct", "nps", "brand_awareness")}, "events": happen[:30]})
    return {"days": out, "from": a, "to": b, "next_day": (co.today + timedelta(days=0)).isoformat()}
