"""Business tools: how the agents read the company's data and take decisions (propose, review, decide).

Everything goes through the Company layer, so numbers, budgets and compliance rules are the same for every agent, and
every decision shows up in the 3D UI (speech bubbles, the decisions board, the strategy log).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from hq.agents.roster import AGENTS, DEPARTMENTS
from hq.company import initiatives as im
from hq.company.catalog import CHANNELS, TARGETS
from hq.core.world import World

log = logging.getLogger("hq.biz_tools")
DECIDERS = {"exec.priya", "exec.daniel"}
REVIEW_DEPTS = {"risk", "exec"}


def _trim(rows: list[dict[str, Any]], n: int = 15) -> list[dict[str, Any]]:
    return rows[:n]


def _short(ini: dict[str, Any]) -> dict[str, Any]:
    return {k: ini.get(k) for k in ("id", "title", "kind", "status", "proposer", "dept", "cost_est", "start_date", "end_date")} | {
        "params": ini.get("params"), "headline": ini.get("estimate", {}).get("headline"), "compliance": ini.get("compliance"),
        "reviews": [{"by": r["by"], "verdict": r["verdict"], "comments": r["comments"]} for r in ini.get("reviews", [])],
        "decision": ini.get("decision_note", "")}


def make_biz_tools(agent_id: str, world: World) -> list[Callable]:
    me = AGENTS[agent_id]
    company = world.company
    is_decider = agent_id in DECIDERS
    can_review = me.dept in REVIEW_DEPTS or agent_id == "data.arjun"

    # ------------------------------------------------------------------ reading
    async def get_company_overview() -> dict:
        """Orientation: what the company is, today's date, targets, the regulatory calendar and the plans on offer. Call this once at the start of a task."""
        pr = company.premium_round_context()
        return {
            "company": "AI Company Health: a fictional Australian private health insurer (~4% market share) that also runs dental, optical and physio clinics and health programs.",
            "today": company.today.isoformat(),
            "targets": TARGETS,
            "rules_to_respect": [
                "Community rating: premiums, eligibility and offers cannot depend on health status or claims history (Private Health Insurance Act).",
                "Existing members' premiums can only change in the annual premium round effective 1 April; discounts are for new joiners only.",
                "Hospital plans must be Gold, Silver, Bronze or Basic (government tiers). Health information is sensitive under the Privacy Act.",
                "ASIC: no misleading claims. Marketing must not target under-18s."],
            "calendar": {"premium_round_effective": pr["effective"], "days_to_premium_round": pr["days_to_go"], "end_of_financial_year": "30 June (tax-time demand surge)",
                         "winter_claims": "June-August hospital and flu season", "extras_peak": "November-December (annual limits reset 1 January)"},
            "plans": [f"{p['id']}: {p['name']} ${p['monthly_price']:.0f}/mo" for p in company.products_view() if p["active"]],
            "channels": list(CHANNELS),
            "your_role": f"{me.name}, {me.role} ({DEPARTMENTS[me.dept].name})",
        }

    async def get_kpis(window_days: int = 7) -> dict:
        """Headline KPIs over the last N days (1-90) with the change versus the previous N days and whether each target is met. Includes sales, cancellations, loss ratio, margin, claims SLA, wait time, NPS, headcount and engagement."""
        return company.kpi_window(max(1, min(int(window_days), 90)))

    async def get_alerts() -> list:
        """Current rule-based alerts (SLA breaches, long waits, sales drops, loss ratio, capacity, attrition, market events), highest severity first."""
        return _trim(company.alerts(), 12)

    async def get_breakdown(metric: str, by: str, days: int = 28) -> list:
        """Break a metric down. metric=sales with by=state|channel|product; metric=claims with by=state|claim_type; metric=cancellations with by=product|reason. days is the lookback."""
        return _trim(company.breakdown(by, max(1, min(int(days), 365)), metric), 16)

    async def get_forecast(metric: str = "new_sales", days: int = 7) -> dict:
        """Seasonal-naive forecast for the next N days (metric: new_sales, cancellations, leads, claims_arrivals, calls) from last year's pattern and this year's trend."""
        return company.forecast(metric, max(1, min(int(days), 28)))

    async def query_data(sql: str) -> dict:
        """Run ONE read-only SQL SELECT (SQLite) over: daily_kpi, daily_sales(date,state,channel,product_id,sales,new_premium_pa), daily_sales_age, daily_cancellations(date,product_id,reason,cancellations), daily_claims(date,state,claim_type,claims,benefits_aud), daily_book, daily_leads, daily_team(date,dept,headcount,vacancies,exits,utilization,engagement,productivity), events, products, initiatives. Max 200 rows."""
        return company.store.query_readonly(sql, allowed=company.files.allowed_tables(agent_id))

    async def get_products() -> list:
        """The plans we sell: price, members in force, 28-day sales and cancellations, price versus market, inclusions."""
        return [{k: p[k] for k in ("id", "name", "category", "tier", "monthly_price", "in_force", "sales_28d", "cancellations_28d", "price_vs_market", "target", "active")}
                for p in company.products_view()]

    async def get_team_status(dept: str = "") -> dict:
        """Workforce view per department: headcount, open roles, utilisation, engagement, annualised attrition, new starters ramping up, annual cost. Leave dept empty for all."""
        t = company.team_status()
        return t.get(dept) if dept else t

    async def get_budget() -> dict:
        """The annual strategy budget: how much is left to commit to initiatives this financial year."""
        return company.budget()

    async def unit_economics(product_id: str = "") -> dict:
        """Customer lifetime value per plan (contribution margin x expected life). Compare with the cost to win a policy before approving growth spend."""
        return company.unit_economics(product_id or None)

    async def describe_initiative_kinds() -> dict:
        """The kinds of initiative you can propose and the exact parameters (with allowed ranges) each needs."""
        return im.KIND_HELP

    async def list_initiatives(status: str = "") -> list:
        """List initiatives (status: proposed, in_review, approved, running, completed, rejected, cancelled; empty = all, newest first)."""
        return [_short(i) for i in _trim(company.list_initiatives(status or None), 15)]

    async def evaluate_initiative(initiative_id: str) -> dict:
        """After-the-fact evaluation of a started initiative: before/after on the metrics it should move, adjusted for last year's seasonality, versus what was expected."""
        return company.evaluate(initiative_id)

    async def premium_round_info() -> dict:
        """The annual premium round (effective 1 April): the approved industry cap, the market price index, days to go, and members by plan."""
        ctx = company.premium_round_context()
        ctx["members_by_plan"] = {p["id"]: p["in_force"] for p in company.products_view() if p["active"]}
        ctx.pop("weights", None)
        return ctx

    # ------------------------------------------------------------------ writing
    async def write_note(kind: str, title: str, body: str) -> dict:
        """Record a note in the strategy log everyone can read. kind: daily_brief, investigation, standup, weekly_plan, board_note, lesson, people_note. Keep body under 1200 characters."""
        n = {"date": company.today.isoformat(), "author": agent_id, "kind": kind[:30], "title": title[:140], "body": body[:1500]}
        n["id"] = company.store.add_note(n["date"], agent_id, n["kind"], n["title"], n["body"])
        world.biz_note(n)
        world.say(agent_id, f"📝 {title}"[:120], 3000)
        return {"ok": True, "note_id": n["id"]}

    async def propose_initiative(kind: str, title: str, rationale: str, params_json: str) -> dict:
        """Propose a strategic initiative. kind: see describe_initiative_kinds. title: short. rationale: the business case in 2-4 sentences with the numbers that justify it (cite KPIs). params_json: a JSON object string with the parameters for that kind, e.g. '{"dept":"claims","count":12}' or '{"channel":"online_direct","daily_budget":30000,"days":28}'. Returns the costed proposal with the expected effect and compliance check; fix any error and call again."""
        try:
            params = json.loads(params_json) if params_json else {}
            if not isinstance(params, dict):
                raise ValueError("params_json must be a JSON object")
        except (json.JSONDecodeError, ValueError) as e:
            return {"error": f"params_json is not valid JSON object: {e}"}
        ini = company.propose(agent_id, me.dept, kind, title, rationale, params)
        if "error" in ini:
            return ini
        world.biz_initiative(ini)
        world.say(agent_id, f"💡 Proposal {ini['id']}: {title}"[:140], 4500)
        return _short(ini)

    tools: list[Callable] = [get_company_overview, get_kpis, get_alerts, get_breakdown, get_forecast, query_data, get_products, get_team_status,
                             get_budget, unit_economics, describe_initiative_kinds, list_initiatives, evaluate_initiative, premium_round_info,
                             write_note, propose_initiative]

    if can_review:
        async def review_initiative(initiative_id: str, verdict: str, comments: str) -> dict:
            """Review a proposed initiative from your function's point of view. verdict: endorse, concerns or object. comments: 1-3 sentences (compliance risks, cost-benefit, capacity, conditions). Objections on compliance grounds are binding for approval."""
            if verdict not in ("endorse", "concerns", "object"):
                return {"error": "verdict must be endorse, concerns or object"}
            ini = company.review(initiative_id, agent_id, verdict, comments)
            if "error" in ini:
                return ini
            world.biz_initiative(ini)
            world.say(agent_id, f"{ {'endorse':'👍','concerns':'⚠️','object':'⛔'}[verdict] } {initiative_id}: {comments}"[:140], 4000)
            return {"ok": True, "initiative": initiative_id, "reviews": len(ini["reviews"])}
        tools.append(review_initiative)

    if is_decider:
        async def decide_initiative(initiative_id: str, decision: str, note: str) -> dict:
            """Make the executive decision on a proposed initiative: decision is approve or reject; note explains why (1-2 sentences). Approving commits its cost to the strategy budget and schedules it in the business; it fails if it breaks a compliance rule or the budget."""
            if decision not in ("approve", "reject"):
                return {"error": "decision must be approve or reject"}
            ini = company.decide(initiative_id, agent_id, decision, note)
            if "error" in ini:
                return ini
            world.biz_initiative(ini)
            world.say(agent_id, f"{'✅ Approved' if decision == 'approve' else '❌ Rejected'} {initiative_id}: {ini['title']}"[:140], 5000)
            return _short(ini)

        async def submit_premium_round(changes_json: str) -> dict:
            """Decide the annual premium round: changes_json is a JSON object mapping plan id to the fractional price change effective 1 April, e.g. '{"hosp_gold":0.035,"hosp_silver":0.034}'. Plans you leave out stay unchanged. Must respect the approved industry cap."""
            try:
                changes = {k: float(v) for k, v in json.loads(changes_json).items()}
            except (json.JSONDecodeError, ValueError, AttributeError) as e:
                return {"error": f"changes_json must be a JSON object of plan id to fraction: {e}"}
            res = company.submit_premium_round(agent_id, changes)
            if "ok" in res:
                world.say(agent_id, f"✅ Premium round set: +{res['weighted_average_increase']*100:.2f}% avg from {res['effective']}", 6000)
            return res
        tools += [decide_initiative, submit_premium_round]

    # ------------------------------------------------------------------ weekly goals (plan, then reflect on the results)
    async def get_weekly_goals() -> dict:
        """This week's company goals with progress so far, and the reviews of the last weeks (what was met or missed and what we tried)."""
        from hq.quality.goals import METRICS
        return {"this_week": company.goals.for_week(), "recent_reviews": company.goals.reviews(4),
                "metrics": {k: v[1] + (" (higher is better)" if v[2] else " (lower is better)") for k, v in METRICS.items()}}
    tools.append(get_weekly_goals)
    if me.lead or me.dept == "exec":
        async def set_weekly_goals(goals_json: str) -> dict:
            """Set this week's measurable goals. goals_json is a JSON list like '[{"metric":"new_sales","target":4,"owner":"sales.leo","why":"..."}]'. Metrics: see get_weekly_goals. Base targets on recent results and what you learned in past reviews."""
            try:
                goals = json.loads(goals_json)
                assert isinstance(goals, list)
            except (json.JSONDecodeError, AssertionError) as e:
                return {"error": f"goals_json must be a JSON list: {e}"}
            res = company.goals.set(agent_id, goals)
            if res["set"]:
                world.say(agent_id, f"🎯 Goals for {res['week']}: {', '.join(res['set'])}", 5000)
            return res
        tools.append(set_weekly_goals)
    return tools
