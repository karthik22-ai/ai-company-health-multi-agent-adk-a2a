"""Agent quality, realism and observability: goals + reflection, fact-checks, memory digests, traces, evaluations, cover rules, competitors."""
import random
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hq.quality.goals import week_of


def _advance(co, n):
    for _ in range(n):
        co.advance()


async def test_weekly_goals_are_set_reviewed_and_learned_from(town_svc):
    s = town_svc
    co = s.company
    _advance(co, 3)
    res = co.goals.set("exec.priya", [{"metric": "new_sales", "target": 2, "why": "test"}, {"metric": "bogus", "target": 1}])
    assert res["set"] == ["new_sales"] and res["errors"]
    assert co.goals.for_week()[0]["actual_so_far"] is not None
    _advance(co, 7)                                                       # into next week
    run = await s.workflows.start("weekly_goals", {})
    run = await s.workflows.wait(run.id, 60)
    assert run.status == "completed", run.error
    rev = co.goals.reviews(1)[0]
    assert rev["week"] == week_of(co.today - timedelta(days=7)) and rev["goals"][0]["metric"] == "new_sales"
    assert any(f["title"].startswith("Weekly goals review") for f in co.files.list(kind="report")), "the review is a document"
    assert any(m["kind"] == "lesson" for m in s.world.memories("sales.leo", limit=20)), "leaders remember the lesson"
    assert co.goals.for_week(), "this week's goals are set (by the CEO's tool call in the mock)"


async def test_published_documents_are_fact_checked(town_svc):
    s = town_svc
    co = s.company
    _advance(co, 2)
    real = int(co.store.kpis(1)[-1]["policies_in_force"])
    good = co.files.create("report", "Good", "bi.olivia", {"markdown": f"We have {real} members today.", "charts": []})
    bad = co.files.create("report", "Bad", "bi.olivia", {"markdown": f"We now have {real + 500} members and a loss ratio of 1% overall.", "charts": []})
    assert co.guard.get(good["id"])["ok"] and co.guard.get(good["id"])["checked"] >= 1
    chk = co.guard.get(bad["id"])
    assert not chk["ok"] and {m["kind"] for m in chk["mismatches"]} >= {"members"}
    assert any("did not match the data" in m["text"] for m in s.world.memories("bi.olivia", limit=10)), "the author learns from it"


async def test_memory_digest_and_relevant_recall(town_svc):
    w = town_svc.world
    for i in range(60):
        w.remember("sales.leo", "work", f"Routine note number {i}", .3 if i % 10 else .9)
    w.remember("sales.leo", "work", "The BLUEGUM campaign targets young families in Riverside", .5)
    assert w.consolidate("sales.leo") and not w.consolidate("sales.leo")
    block = w.memory_block("sales.leo", query="what about the bluegum campaign?")
    assert "summary" in block and "BLUEGUM" in block


async def test_agent_runs_are_traced_with_their_tool_calls(town_svc):
    s = town_svc
    t = s.world.new_task("mkt.grace", "Town campaign", "Grow in the town")
    await s.runtime.run_task(t, mock={"biz": "town_campaign"})
    from hq.quality import traces
    rows = traces.list_traces(s.company.store, agent="mkt.grace")
    assert rows and rows[0]["status"] == "ok" and "get_town_insights" in rows[0]["tools"]
    full = traces.get_trace(s.company.store, rows[0]["id"])
    assert full["prompt"] and any("result_of" in st for st in full["steps"])
    assert traces.summary(s.company.store, 60)["runs"] >= 1


async def test_evaluation_runs_and_scores(town_svc):
    from hq.quality.evals import CASES, Evals, score
    s = town_svc
    _advance(s.company, 2)
    out = await Evals(s).run(cases=["members", "community_rating", "memory"])
    assert out["total"] == 3 and 0 <= out["score"] <= 1 and Evals(s).history(1)[0]["total"] == 3
    members = next(c for c in CASES if c["id"] == "members")
    n = int(s.company.store.kpis(1)[-1]["policies_in_force"])
    assert score(members, f"We have {n} policies in force.", s.company)["pass"]
    assert not score(members, f"We have {n + 400} policies.", s.company)["pass"]
    assert score(next(c for c in CASES if c["id"] == "community_rating"), "No, community rating means everyone pays the same.", s.company)["pass"]


async def test_waiting_periods_extras_limits_complaints_and_word_of_mouth(town_svc):
    co = town_svc.company
    town, h = co.town, co.town.health
    r = next(x for x in town.residents() if (x.get("cover") or {}).get("extras"))
    new = dict(r, cover=dict(r["cover"], since=co.today.isoformat(), transferred=False))
    v = h.visit(new, "dental", co.today, random.Random(1))
    assert v["benefit"] == 0 and v["gap"] == v["cost"] and "waiting period" in v["text"]
    old = dict(r, cover=dict(r["cover"], transferred=True))
    paid = sum(h.visit(old, "optical", co.today, random.Random(i))["benefit"] for i in range(4))
    assert paid <= 250, "annual optical limit"
    for i in range(40):                                                    # big gaps → some complaints and warnings to friends
        h.aftermath(r, "medibank", "Medibank", "surgery", 2000, False, 0, random.Random(i))
    kinds = {e["kind"] for e in co.store.rows("SELECT kind FROM town_events WHERE resident=?", (r["id"],))}
    assert "complaint" in kinds and ("word_of_mouth" in kinds or not [x for x in town.relations(r["id"]) if not x.get("employee")])
    assert any(x["stars"] == 1 for x in co.store.rows("SELECT stars FROM town_reviews WHERE resident=?", (r["id"],)))


async def test_competitors_respond_and_change_the_comparison_site(town_svc):
    co = town_svc.company
    town = co.town

    class Always(random.Random):
        def random(self):
            return 0.0
    moves = town.competitors.step(co.today, Always(3))
    assert moves and all(m["kind"] == "competitor" for m in moves)
    act = town.competitors.active()
    ins, mv = next(iter(act.items()))
    r = town.residents()[0]
    offers = [c for c in town.comparison(r) if c["insurer"] == ins]
    if mv["type"] in ("offer", "price"):
        assert offers and mv["text"] in offers[0]["offer"]
    assert "Competitor moves running now" in town_svc.runtime.factory.market_block()


async def test_quality_api(town_svc):
    from hq.api.routes.quality import router
    from hq.api.routes.work import router as work_router
    _advance(town_svc.company, 3)
    app = FastAPI()
    app.state.svc = town_svc
    app.include_router(router)
    app.include_router(work_router)
    c = TestClient(app)
    for path in ("/api/ops", "/api/traces", "/api/goals", "/api/evals", "/api/timeline?days=7"):
        assert c.get(path).status_code == 200, path
    tl = c.get("/api/timeline?days=7").json()
    assert len(tl["days"]) == 3 and "kpi" in tl["days"][0]
    assert "gate" in c.get("/api/ops").json()
    f = town_svc.company.files.create("report", "X", "bi.olivia", {"markdown": "We have 9999 members.", "charts": []})
    assert c.get(f"/api/files/{f['id']}").json()["check"]["ok"] is False
    assert next(x for x in c.get("/api/files").json() if x["id"] == f["id"])["check"]["ok"] is False
