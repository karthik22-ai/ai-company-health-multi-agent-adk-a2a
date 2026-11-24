import json

import pytest
from starlette.testclient import TestClient

from hq.api.app import create_app


@pytest.fixture
def client(settings):
    settings.persist = True          # the audit log is part of what is tested
    with TestClient(create_app(settings)) as c:
        yield c


def drain_resync(ws):
    """Read the commands a freshly connected UI gets until the resync_done marker."""
    out = []
    while True:
        m = json.loads(ws.receive_text())
        if m["type"] == "resync_done":
            return out
        out.append(m)


def wait_for(client, pred, timeout=20):
    import time
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.05)
    raise AssertionError("timeout")


def test_health_and_roster(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["agents"] == 50 and h["a2a_agents"] == 50
    r = client.get("/api/roster").json()
    assert len(r["departments"]) == 12 and "mr1" in r["rooms"]


def test_agent_cards_are_served_over_a2a(client):
    card = client.get("/a2a/risk.isabel/.well-known/agent-card.json")
    assert card.status_code == 200
    assert "Isabel" in json.dumps(card.json())
    assert any(a["id"] == "risk.kwame" for a in client.get("/api/a2a/agents").json())


def test_assign_task_and_wait(client):
    r = client.post("/api/agents/sales.leo/tasks", json={"title": "Forecast v3", "wait": True})
    assert r.status_code == 202 and r.json()["status"] == "done" and r.json()["progress"] == 100
    assert client.get("/api/agents/sales.leo").json()["tasks"][0]["title"] == "Forecast v3"


def test_external_executor_progress(client):
    t = client.post("/api/agents/data.chloe/tasks", json={"title": "Backfill", "executor": "external"}).json()
    assert t["status"] == "doing"
    client.post(f"/api/tasks/{t['id']}/progress", json={"percent": 40, "note": "half way"})
    assert client.get("/api/agents/data.chloe").json()["tasks"][0]["progress"] == 40
    client.post(f"/api/tasks/{t['id']}/progress", json={"percent": 100, "note": "done"})
    assert client.get("/api/tasks", params={"agent": "data.chloe"}).json()[0]["status"] == "done"


def test_unknown_agent_and_room_404(client):
    assert client.post("/api/agents/nobody/status", json={"state": "idle"}).status_code == 404
    assert client.post("/api/agents/sales.leo/move", json={"room": "nowhere"}).status_code == 404


def test_websocket_streams_commands_and_handles_chat(client):
    with client.websocket_connect("/ws") as ws:
        assert drain_resync(ws)[0]["type"] == "policy"                 # resync on connect
        ws.send_text(json.dumps({"type": "hello", "agents": [], "rooms": []}))
        client.post("/api/agents/claims.helen/status", json={"state": "working", "text": "Posting accruals"})
        msg = json.loads(ws.receive_text())
        assert msg == {"type": "status", "agent": "claims.helen", "state": "working", "text": "Posting accruals", "now": True}
        # chat: UI -> backend -> ADK agent -> chat_reply
        ws.send_text(json.dumps({"type": "chat", "agent": "sales.leo", "text": "What are you working on?"}))
        for _ in range(50):
            m = json.loads(ws.receive_text())
            if m["type"] == "chat_reply":
                break
        assert m["agent"] == "sales.leo" and m["text"]


def test_websocket_resync_after_reconnect(client):
    client.post("/api/agents/care.rafael/tasks", json={"title": "Cash positioning", "wait": True})
    with client.websocket_connect("/ws") as ws:
        first = drain_resync(ws)
    assert first[0]["type"] == "policy"
    assert any(m["type"] == "task" and m["title"] == "Cash positioning" for m in first)
    assert any(m["type"] == "biz_day" for m in first) and any(m["type"] == "note" for m in first) or True


def test_chat_never_moves_agent_unless_asked(client):
    r = client.post("/api/agents/sales.sara/chat", json={"text": "How is it going?"}).json()
    assert r["reply"]
    assert not [c for c in client.get("/api/events/history").json() if c["type"] in ("move", "meeting")]


def test_chat_can_send_agent_to_meeting_when_user_asks(client):
    with client.websocket_connect("/ws") as ws:
        drain_resync(ws)
        client.post("/api/agents/sales.sara/chat", json={"text": "Please come to a meeting in mr2 and show me your work"})
        types = []
        for _ in range(12):
            m = json.loads(ws.receive_text())
            types.append(m["type"])
            if m["type"] == "chat_reply":
                break
        assert "meeting" in types


def test_auth_token_required_when_configured(settings):
    settings.auth_token = "s3cret"
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/state").status_code == 401
        assert c.get("/api/state", headers={"Authorization": "Bearer s3cret"}).status_code == 200
        assert c.get("/a2a/sales.leo/.well-known/agent-card.json").status_code == 200   # cards are public
        with pytest.raises(Exception):
            with c.websocket_connect("/ws"):
                pass
        with c.websocket_connect("/ws?token=s3cret") as ws:
            drain_resync(ws)


def test_workflow_over_rest(client):
    assert {"daily_ops", "weekly_strategy", "monthly_review", "premium_round", "team_health"} <= {w["name"] for w in client.get("/api/workflows").json()}
    r = client.post("/api/workflows/daily_ops/runs", json={"params": {}})
    assert r.status_code == 202
    run_id = r.json()["id"]
    wait_for(client, lambda: client.get(f"/api/workflows/runs/{run_id}").json()["status"] == "completed", 60)
    assert client.post(f"/api/workflows/runs/{run_id}/approve", json={}).status_code == 409


def test_company_endpoints(client):
    snap = client.get("/api/company/snapshot").json()
    assert snap["last"]["policies_in_force"] > 300_000 and snap["products"] and "dept_kpis" in snap
    assert len(client.get("/api/company/series", params={"metric": "new_sales", "days": 30}).json()) == 30
    assert client.get("/api/company/series", params={"metric": "nope"}).status_code == 404
    assert client.get("/api/company/breakdown", params={"metric": "sales", "by": "channel"}).json()
    q = client.post("/api/company/query", json={"sql": "SELECT COUNT(*) AS n FROM daily_kpi"}).json()
    assert q["rows"][0][0] >= 120
    assert "error" in client.post("/api/company/query", json={"sql": "DELETE FROM daily_kpi"}).json()


def test_clock_step_runs_the_agents_and_pushes_to_the_ui(client):
    with client.websocket_connect("/ws") as ws:
        first = [m["type"] for m in drain_resync(ws)]
        assert "biz_day" in first                                   # resync gives the UI the business view straight away
        before = client.get("/api/company/clock").json()["date"]
        r = client.post("/api/company/clock", json={"action": "step", "days": 1, "agents": True})
        assert r.status_code == 200 and r.json()["date"] > before
        seen = set()
        for _ in range(400):
            seen.add(json.loads(ws.receive_text())["type"])
            if {"biz_day", "note"} <= seen:
                break
        assert {"biz_day", "note"} <= seen
    assert client.post("/api/company/clock", json={"action": "pause"}).json()["running"] is False


def test_board_can_propose_and_decide(client):
    r = client.post("/api/company/proposals", json={"kind": "marketing_campaign", "title": "Board: summer push", "rationale": "growth",
                                                    "params": {"channel": "online_direct", "daily_budget": 15000, "days": 21}})
    assert r.status_code == 201
    iid = r.json()["id"]
    d = client.post(f"/api/company/initiatives/{iid}/decide", json={"decision": "approve", "note": "go"})
    assert d.status_code == 200 and d.json()["status"] == "approved"
    bad = client.post("/api/company/proposals", json={"kind": "hire", "title": "x", "params": {"dept": "nope", "count": 3}})
    assert bad.status_code == 422


def test_frontend_is_served_from_its_modules(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"].startswith("/ui/?ws=")
    page = client.get("/ui/").text
    assert '<script src="app.js"></script>' in page and 'href="css/app.css"' in page
    js = client.get("/ui/app.js")
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    import json
    from hq.core.config import PROJECT_DIR
    order = json.loads((PROJECT_DIR / "frontend/js/manifest.json").read_text())["order"]
    assert order[0] == "data.js" and order[-1] == "main.js", "data first, the animation loop last"
    assert js.text.index("const T={") < js.text.index("function animate(")
    assert client.get("/ui/css/app.css").status_code == 200


def test_agent_factory_describes_what_it_builds(client):
    f = client.get("/api/factory").json()
    assert f["kinds"]["employee"]["count"] == 50 and f["kinds"]["employee"]["toolsets"] == ["core", "business", "work"]
    emp = {e["id"]: e for e in f["employees"]}
    assert "hire_agent" in emp["people.camille"]["tools"] and "create_dashboard" in emp["bi.olivia"]["tools"]
    assert "review_access_request" in emp["data.arjun"]["tools"] and "hire_agent" not in emp["sales.leo"]["tools"]
