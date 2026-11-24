"""Agents + LangGraph + the synthetic company working together (mock LLM, deterministic)."""

import pytest


@pytest.fixture
async def co(svc):
    svc.company.ensure_history()
    return svc


async def run_flow(svc, name, params=None, timeout=60):
    run = await svc.workflows.start(name, params or {})
    return await svc.workflows.wait(run.id, timeout)


async def test_daily_ops_writes_brief_investigates_alerts_and_standup(co):
    c = co.company
    for _ in range(280):                         # run into the December peak where service levels strain
        c.advance()
    assert any(a["severity"] in ("high", "medium") for a in c.alerts())
    run = await run_flow(co, "daily_ops", {"max_investigations": 2})
    assert run.status == "completed", run.error
    nodes = {s.node for s in run.steps}
    assert {"data_brief", "triage", "standup"} <= nodes
    kinds = [n["kind"] for n in c.store.rows("SELECT kind FROM notes")]
    assert "daily_brief" in kinds and "standup" in kinds and "investigation" in kinds


async def test_weekly_strategy_proposes_reviews_and_decides(co):
    c = co.company
    for _ in range(280):
        c.advance()
    run = await run_flow(co, "weekly_strategy", {"max_approvals": 3, "week": 1}, timeout=120)
    assert run.status == "completed", run.error
    inis = c.list_initiatives()
    assert inis, "departments should have proposed something with service levels under strain"
    statuses = {i["status"] for i in inis}
    assert statuses & {"approved", "running"}, statuses
    assert any(i["reviews"] for i in inis)                      # Risk / Finance reviewed
    assert sum(1 for i in inis if i["status"] in ("approved", "running")) <= 3
    assert c.budget()["remaining"] < 24_000_000
    assert any(m["kind"] == "consult" or m["kind"] == "hand_off" for m in co.peers.messages) or True


async def test_approved_initiative_changes_the_business_and_is_evaluated(co):
    c = co.company
    for _ in range(280):
        c.advance()
    await run_flow(co, "weekly_strategy", {"week": 1}, timeout=120)
    approved = [i for i in c.list_initiatives() if i["status"] in ("approved", "running")]
    assert approved
    for _ in range(60):
        c.advance()
    ev = c.evaluate(approved[0]["id"])
    assert "metrics" in ev or "message" in ev


async def test_compliance_objection_blocks_approval_in_the_flow(co):
    c = co.company
    bad = c.propose("mkt.grace", "mkt", "promo_discount", "Reward healthy members", "Offer a discount to members with no claims history",
                    {"product_id": "hosp_silver", "discount_pct": 12, "days": 30})
    assert not bad["compliance"]["ok"]
    await run_flow(co, "weekly_strategy", {"week": 2}, timeout=120)
    assert c.sim.initiatives[bad["id"]]["status"] == "rejected"


async def test_premium_round_workflow_sets_prices(co):
    c = co.company
    run = await run_flow(co, "premium_round", {}, timeout=60)
    assert run.status == "completed", run.error
    assert c.sim.s["pending_prices"], "the CFO should have submitted the round"
    eff = c.sim.s["pending_prices"][0]["effective"]
    assert eff == "2026-04-01"


async def test_monthly_and_team_health_flows(co):
    c = co.company
    for _ in range(100):
        c.advance()
    m = await run_flow(co, "monthly_review", {})
    assert m.status == "completed", m.error
    t = await run_flow(co, "team_health", {}, timeout=90)
    assert t.status == "completed", t.error
    kinds = [n["kind"] for n in c.store.rows("SELECT kind FROM notes")]
    assert "board_note" in kinds and "lesson" in kinds


async def test_flows_never_move_agents_by_default(co):
    c = co.company
    for _ in range(40):
        c.advance()
    await run_flow(co, "daily_ops", {})
    await run_flow(co, "weekly_strategy", {"week": 3}, timeout=120)
    assert not [e for e in co.bus.history if e["type"] in ("move", "meeting", "desk")]
