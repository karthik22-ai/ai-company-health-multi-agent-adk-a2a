"""Teams' real work on the synthetic data: data access governance, dashboards, apps, agenda meetings, hiring, downloads."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hq.agents.roster import AGENTS, DEPARTMENTS
from hq.work import render


@pytest.fixture
async def co(svc):
    svc.company.ensure_history()
    return svc


async def run_flow(svc, name, params=None, timeout=90):
    run = await svc.workflows.start(name, params or {})
    return await svc.workflows.wait(run.id, timeout)


def _remove_hires(before: set[str]) -> None:
    for aid in set(AGENTS) - before:
        spec = AGENTS.pop(aid)
        DEPARTMENTS[spec.dept].agents[:] = [a for a in DEPARTMENTS[spec.dept].agents if a.id != aid]


async def test_data_access_is_enforced_and_granted_by_the_data_team(co):
    files, store = co.company.files, co.company.store
    sql = "SELECT dept, AVG(engagement) FROM daily_team GROUP BY dept"
    assert "daily_team" not in files.allowed_tables("sales.wei")
    denied = store.query_readonly(sql, allowed=files.allowed_tables("sales.wei"))
    assert "Access denied" in denied["error"] and denied["denied"] == ["daily_team"]
    assert "rows" in store.query_readonly(sql, allowed=files.allowed_tables("people.hugo"))   # HR data is People's by default
    req = files.request_access("sales.wei", "daily_team", "Need sales team attrition to plan phone-sales capacity for the June peak")
    assert req["status"] == "pending"
    run = await run_flow(co, "access_review")
    assert run.status == "completed", run.error
    assert files.access_requests("pending") == []
    assert "daily_team" in files.allowed_tables("sales.wei")
    assert "rows" in store.query_readonly(sql, allowed=files.allowed_tables("sales.wei"))
    g = files.grants()[0]
    assert g["subject"] == "sales.wei" and g["granted_by"].startswith("data.")


async def test_reporting_cycle_publishes_dashboards_and_report_with_real_rows(co):
    run = await run_flow(co, "reporting_cycle", {"week": 0})
    assert run.status == "completed", run.error
    files = co.company.files
    dashes = files.list(kind="dashboard")
    assert len(dashes) >= 2 and all(d["dept"] == "bi" for d in dashes)
    full = files.get(dashes[0]["id"])
    ch = full["content"]["charts"][0]
    assert ch["rows"] and ch["columns"] and ch["sql"].lower().startswith("select")
    last = co.company.store.last_date()
    assert any(str(r[0]) == last for c in full["content"]["charts"] for r in c["rows"] if c["x"] == "date"), "dashboards use the live data"
    assert files.list(kind="report"), "the weekly report is published"
    html = render.to_html(full)
    assert "<svg" in html and full["title"] in html
    assert dashes[0]["id"] in {f["id"] for f in files.list(dept="bi")}


async def test_it_builds_a_sandboxed_app_with_injected_data(co):
    run = await run_flow(co, "it_build", {"n": 1})
    assert run.status == "completed", run.error
    app = co.company.files.list(kind="app")[0]
    full = co.company.files.get(app["id"])
    assert full["dept"] == "it" and full["content"]["data"]
    page = render.app_html(full)
    assert "window.HQ_DATA=" in page and "fetch(" not in page


async def test_agenda_meeting_decks_presentations_and_minutes(co):
    events = []
    q = co.bus.subscribe()
    attendees = ["sales.leo", "claims.helen", "bi.olivia"]
    run = await run_flow(co, "meeting", {"room": "mr2", "agenda": "Why are net adds below target and what do we do this month?", "attendees": attendees})
    assert run.status == "completed", run.error
    while not q.empty():
        events.append(q.get_nowait())
    files = co.company.files
    mid = run.result["outputs"]["meeting"]
    decks = files.list(meeting=mid, kind="presentation")
    assert {d["author"] for d in decks} == set(attendees)
    presented = [e for e in events if e.get("type") == "present"]
    assert len(presented) == 3 and any(s.get("chart") for e in presented for s in e["slides"]), "decks with real charts reach the room screen"
    assert files.list(meeting=mid, kind="minutes"), "minutes are written and linked to the meeting"
    done = [e for e in events if e.get("type") == "meeting_done"]
    assert done and len(done[0]["files"]) == 4
    pptx = render.to_pptx(files.get(decks[0]["id"]))
    assert pptx and pptx[:2] == b"PK", "decks download as real PowerPoint files"


async def test_people_team_hires_a_real_new_agent(co):
    before = set(AGENTS)
    try:
        q = co.bus.subscribe()
        run = await run_flow(co, "work_request", {"dept": "people", "text": "We need a fraud analytics specialist in Claims"})
        assert run.status == "completed", run.error
        new = set(AGENTS) - before
        assert len(new) == 1
        aid = new.pop()
        assert aid.startswith("claims.") or aid.startswith("people.") or "." in aid
        assert aid in co.world.agents and aid in co.runtime.runners, "the hire is a working ADK agent"
        hires = co.company.files.hires()
        assert hires and hires[0]["id"] == aid
        evs = []
        while not q.empty():
            evs.append(q.get_nowait())
        assert any(e.get("type") == "hire" and e["agent"]["id"] == aid for e in evs)
        # the new colleague can actually work
        t = co.world.new_task(aid, "First day", "Introduce yourself to the team")
        await co.runtime.run_task(t)
        assert co.world.tasks[t.id].status == "done"
    finally:
        _remove_hires(before)


async def test_download_api_serves_html_md_csv_pptx(co, settings):
    await run_flow(co, "reporting_cycle", {"week": 1})
    from hq.api.routes.work import router
    app = FastAPI()
    app.state.svc = co
    app.include_router(router)
    c = TestClient(app)
    fid = c.get("/api/files?kind=dashboard").json()[0]["id"]
    assert c.get(f"/api/files/{fid}").json()["content"]["charts"]
    for fmt, ctype in (("html", "text/html"), ("md", "text/plain"), ("csv", "text/csv"), ("pptx", "presentation")):
        r = c.get(f"/api/files/{fid}/download?fmt={fmt}")
        assert r.status_code == 200 and ctype in r.headers["content-type"], (fmt, r.status_code, r.text[:200])
        assert "attachment" in r.headers["content-disposition"]
    acc = c.get("/api/access").json()
    assert {d["dataset"] for d in acc["datasets"]} >= {"daily_team", "daily_claims"}
    assert json.loads(c.get("/api/access/sales.wei").content)


async def test_it_builds_apps_from_real_needs_and_tells_the_requester(co):
    ar = co.company.app_requests
    from hq.agents.tools.work import make_work_tools
    tools = {t.__name__: t for t in make_work_tools("claims.helen", co.world)}
    assert "request_app" in tools and "create_app" not in tools, "everyone can ask; only IT builds"
    res = await tools["request_app"]("Claims triage board", "Claims leads need today's backlog by claim type to assign assessors each morning.",
                                     "daily_claims, daily_kpi", "Backlog cleared faster; SLA back above 90%")
    rid = res["request_id"]
    again = await tools["request_app"]("Claims triage board", "Same thing asked twice by another colleague in the team.")
    assert again["request_id"] == rid, "duplicates are merged"
    co.company.store.set_kv("app_signal_milestone", 0)
    run = await run_flow(co, "it_build", {"n": 0})
    assert run.status == "completed", run.error
    raised = ar.list(None, 50)
    assert any(r["source"] == "signal" and r["title"] == "Membership growth tracker" for r in raised), "growth raises a request"
    done = [r for r in raised if r["status"] == "done"]
    assert len(done) == 1 and done[0]["file_id"], "the top-ranked request was built"
    app = co.company.files.get(done[0]["file_id"])
    assert app["kind"] == "app" and app["content"]["data"]
    assert any(r["priority"] > 0 for r in raised), "the Head of IT ranked the backlog"
    requester = done[0]["requester"]
    assert any("IT built the app I asked for" in m["text"] for m in co.world.memories(requester, limit=20)), "the team that asked is told"
    assert not ar.scan_signals() or all(r["signal"] != "growth" for r in ar.scan_signals()), "the same milestone is not raised twice"


async def test_ceo_request_to_it_goes_on_the_backlog(co):
    run = await run_flow(co, "it_build", {"request": "A calculator that shows members what each plan costs them per month after the rebate"})
    assert run.status == "completed", run.error
    r = [x for x in co.company.app_requests.list(None) if x["source"] == "ceo"][0]
    assert r["status"] == "done" and co.company.files.get(r["file_id"])["kind"] == "app", "the CEO's request is built first"
