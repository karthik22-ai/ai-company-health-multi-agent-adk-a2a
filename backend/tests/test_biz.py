"""The synthetic company: determinism, calendar effects, and that initiatives move the numbers in the right direction."""
from datetime import date, timedelta

import pytest

from hq.company.company import Company


def make(tmp_path, name="c.db", seed=7, start=date(2026, 3, 2)):
    c = Company(tmp_path / name, seed=seed, start=start)
    c.ensure_history()
    return c


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    return make(tmp_path_factory.mktemp("base"))


def run_days(c, n):
    for _ in range(n):
        c.advance()


def test_history_has_realistic_shape(base):
    w = base.kpi_window(28)["current"]
    assert 380_000 < w["policies_in_force"] < 470_000
    assert 0.82 < w["loss_ratio"] < 0.92
    assert 0.0 < w["margin"] < 0.07
    assert 150 < w["new_sales_per_day"] < 400
    y = base.store.kpis(365)
    assert len(y) == 365 and y[0]["date"] < y[-1]["date"]


def test_plans_follow_australian_tiers(base):
    ids = {p["id"] for p in base.products_view()}
    assert {"hosp_gold", "hosp_silver", "hosp_bronze", "hosp_basic", "combo_young", "ovhc", "oshc"} <= ids
    tiers = {p["tier"] for p in base.products_view() if p["category"] == "hospital"}
    assert tiers == {"gold", "silver", "bronze", "basic"}


def test_seasonality_june_sales_beat_may(base):
    rows = base.store.rows("SELECT substr(date,1,7) m, AVG(new_sales) s FROM daily_kpi GROUP BY 1")
    by = {r["m"]: r["s"] for r in rows}
    assert by["2025-06"] > by["2025-05"] * 1.2


def test_weekends_sell_less_than_weekdays(base):
    r = base.store.rows("SELECT strftime('%w', date) d, AVG(new_sales) s FROM daily_kpi GROUP BY 1")
    d = {x["d"]: x["s"] for x in r}
    assert d["1"] > d["6"] * 1.4 and d["1"] > d["0"] * 1.6


def test_deterministic_for_same_seed(tmp_path):
    a, b = make(tmp_path, "a.db"), make(tmp_path, "b.db")
    run_days(a, 5), run_days(b, 5)
    assert a.store.kpis(5) == b.store.kpis(5)
    c = make(tmp_path, "c.db", seed=99)
    run_days(c, 5)
    assert c.store.kpis(5) != a.store.kpis(5)


def test_read_only_sql_tool_is_safe(base):
    ok = base.store.query_readonly("SELECT date, new_sales FROM daily_kpi ORDER BY date DESC LIMIT 3")
    assert len(ok["rows"]) == 3
    for bad in ["DELETE FROM daily_kpi", "SELECT * FROM kv", "SELECT 1; DROP TABLE daily_kpi", "PRAGMA table_info(daily_kpi)", "INSERT INTO events VALUES (1,2,3,4,5,6,7)"]:
        assert "error" in base.store.query_readonly(bad), bad
    assert base.store.one("SELECT COUNT(*) n FROM daily_kpi")["n"] >= 365


def test_alerts_have_owners_and_messages(base):
    for a in base.alerts():
        assert a["dept"] in {"claims", "care", "sales", "data", "exec", "people", "mkt", "prod", "health", "risk"}
        assert a["message"]


def test_marketing_campaign_adds_leads(tmp_path):
    a, b = make(tmp_path, "a.db"), make(tmp_path, "b.db")
    ini = b.propose("sales.leo", "sales", "marketing_campaign", "Online push", "more leads", {"channel": "online_direct", "daily_budget": 40000, "days": 30})
    assert b.decide(ini["id"], "exec.priya", "approve", "go")["status"] == "approved"
    run_days(a, 30), run_days(b, 30)
    la = a.kpi_window(14)["current"]["leads_per_day"]
    lb = b.kpi_window(14)["current"]["leads_per_day"]
    assert lb > la * 1.15


def test_hiring_reduces_claims_backlog_pressure(tmp_path):
    a, b = make(tmp_path, "a.db", start=date(2026, 11, 2)), make(tmp_path, "b.db", start=date(2026, 11, 2))
    ini = b.propose("claims.helen", "claims", "hire", "More assessors", "peak season", {"dept": "claims", "count": 20})
    b.decide(ini["id"], "exec.priya", "approve", "ok")
    run_days(a, 80), run_days(b, 80)
    wa, wb = a.kpi_window(14)["current"], b.kpi_window(14)["current"]
    assert wb["claims_sla_pct"] >= wa["claims_sla_pct"]
    assert wb["claims_utilization"] < wa["claims_utilization"]
    assert b.team_status()["claims"]["headcount"] > a.team_status()["claims"]["headcount"]


def test_new_product_launches_and_sells(tmp_path):
    c = make(tmp_path)
    ini = c.propose("prod.elena", "prod", "new_product", "Flex Silver", "digital-first plan", {
        "name": "Flex Silver", "category": "hospital", "tier": "silver", "monthly_price": 175, "expected_share": 0.06, "target": "digital natives", "description": "flexible"})
    assert "error" not in ini, ini
    c.decide(ini["id"], "exec.priya", "approve", "launch")
    run_days(c, 60)
    p = next(p for p in c.products_view() if p["name"] == "Flex Silver")
    assert p["in_force"] > 100


def test_compliance_blocks_health_status_targeting(tmp_path):
    c = make(tmp_path)
    ini = c.propose("mkt.grace", "mkt", "promo_discount", "Discount healthy members", "Offer a 15% discount to members with no claims history", {"product_id": "hosp_silver", "discount_pct": 15, "days": 30})
    assert not ini["compliance"]["ok"]
    res = c.decide(ini["id"], "exec.priya", "approve", "yes")
    assert "error" in res and "community rating" in res["error"].lower()


def test_budget_is_committed_on_approval(tmp_path):
    c = make(tmp_path)
    before = c.budget()["remaining"]
    ini = c.propose("mkt.grace", "mkt", "marketing_campaign", "Comparison push", "x", {"channel": "comparison_site", "daily_budget": 20000, "days": 20})
    c.decide(ini["id"], "exec.priya", "approve", "ok")
    assert c.budget()["remaining"] == before - ini["cost_est"]


def test_premium_round_rules(tmp_path):
    c = make(tmp_path)           # starts 2 March 2026: within 45 days of 1 April
    ctx = c.premium_round_context()
    assert ctx["effective"] == "2026-04-01"
    too_high = {p: 0.09 for p in c.sim.products}
    assert "error" in c.submit_premium_round("exec.daniel", too_high)
    ok = {p: 0.034 for p in c.sim.products}
    assert c.submit_premium_round("exec.daniel", ok)["ok"]
    before = c.sim.s["price_idx"]["hosp_gold"]
    run_days(c, 31)
    assert c.sim.s["price_idx"]["hosp_gold"] / before == pytest.approx(1.034, rel=1e-3)


def test_april_first_raises_calls_and_cancellations(tmp_path):
    c = make(tmp_path)
    run_days(c, 40)
    rows = {r["date"]: r for r in c.store.kpis(40)}
    before = sum(rows[(date(2026, 3, 20) + timedelta(days=i)).isoformat()]["calls"] for i in range(7)) / 7
    after = sum(rows[(date(2026, 4, 2) + timedelta(days=i)).isoformat()]["calls"] for i in range(7)) / 7
    assert after > before * 1.15


def test_evaluate_reports_effect(tmp_path):
    c = make(tmp_path)
    ini = c.propose("sales.leo", "sales", "marketing_campaign", "Online push", "x", {"channel": "online_direct", "daily_budget": 30000, "days": 20})
    c.decide(ini["id"], "exec.priya", "approve", "go")
    run_days(c, 25)
    ev = c.evaluate(ini["id"])
    assert ev["metrics"]["leads"]["change_pct_naive"] > 5
