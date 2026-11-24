"""The operating rhythm of the company as LangGraph workflows.

  daily_ops        every simulated day   brief → triage → (fan-out: one investigation per alert) → urgent decision → stand-up
  weekly_strategy  every Monday          brief → 7 departments propose in parallel → Risk + Finance challenge in parallel → CEO decides → plan
  monthly_review   1st of the month      evaluate running initiatives (before/after) → board summary → (board meeting)
  premium_round    mid-Feb               actuary view → pricing proposal → compliance check → CEO/CFO decide → member comms
  team_health      mid-month             engagement review → people plan → CFO review → CEO decides

Departments propose; Risk & Compliance and Finance challenge (using A2A to question proposers); the executives decide. Approved initiatives
change the simulated business, and the next review measures what actually happened.
"""
from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from hq.agents.roster import dept_lead
from hq.workflows.base import Ctx, merge_dict

PROPOSERS = ["sales", "mkt", "claims", "care", "prod", "health", "people"]
TOOLS_HINT = ("Use your tools: get_membership_funnel and get_town_insights (how we win and lose members in Wattle Grove), get_kpis, get_alerts, query_data, "
              "list_initiatives, evaluate_initiative. The goal is more members: propose concrete tactics and learn from what worked before. Cite the numbers you used.")


class FlowState(TypedDict, total=False):
    params: dict[str, Any]
    outputs: Annotated[dict[str, str], merge_dict]
    alerts: list[dict[str, Any]]
    alert: dict[str, Any]
    proposals: Annotated[list[str], operator.add]


def _today(ctx: Ctx) -> str:
    return ctx.svc.company.today.isoformat() if ctx.svc.company else ""


# =============================================================================== daily
def build_daily(ctx: Ctx):
    P = ctx.run.params
    co = ctx.svc.company

    @ctx.step("data_brief", "Daily data brief")
    async def data_brief(state: FlowState):
        t = await ctx.assign("data_brief", "data.arjun", f"Daily brief for {_today(ctx)}",
                             "Produce today's trading brief for the executive team. " + TOOLS_HINT + " Cover: sales vs the 7-day forecast, cancellations, loss ratio, claims SLA and backlog, "
                             "call waits, NPS, any market events. Then call write_note with kind='daily_brief' (under 900 characters), listing the top issues.",
                             mock={"biz": "brief"})
        return {"outputs": {"data_brief": t.result or ""}}

    @ctx.step("triage", "Triage alerts")
    async def triage(state: FlowState):
        cool = co.store.get_kv("alert_cooldown", {})
        today = co.today
        picks = []
        for a in co.alerts():
            if a["severity"] == "info":
                continue
            last = cool.get(a["key"])
            if last and (today - date.fromisoformat(last)).days < int(P.get("cooldown_days", 5)):
                continue
            picks.append(a)
        picks = picks[: int(P.get("max_investigations", 2))]
        for a in picks:
            cool[a["key"]] = today.isoformat()
        co.store.set_kv("alert_cooldown", cool)
        ctx.world.log(f"Triage: {len(picks)} alert(s) to investigate" if picks else "Triage: nothing above threshold")
        return {"alerts": picks}

    def route(state: FlowState):
        alerts = state.get("alerts") or []
        return [Send("investigate", {"alert": a, "params": P, "outputs": {}}) for a in alerts] or "urgent_decision"

    @ctx.step("investigate", "Investigate alerts")
    async def investigate(state: FlowState):
        a = state["alert"]
        lead = dept_lead(a["dept"] if a["dept"] != "exec" else "data")
        t = await ctx.assign("investigate", lead.id, f"Investigate: {a['key'].replace('_', ' ')}",
                             f"An alert fired: {a['message']} Find the root cause with data (use get_breakdown, query_data, get_team_status) and write a note with kind='investigation'. "
                             "If it is HIGH severity and needs urgent action (e.g. capacity), propose ONE costed initiative with propose_initiative; otherwise leave proposals for the weekly strategy meeting.",
                             mock={"biz": "investigate", "alert": a, "allow_proposal": True})
        return {"outputs": {f"investigate_{a['key']}": t.result or ""}}

    @ctx.step("urgent_decision", "Urgent decisions")
    async def urgent_decision(state: FlowState):
        pending = [i for i in co.list_initiatives("proposed") if i["created"] == co.today.isoformat()]
        if not pending:
            return {"outputs": {"urgent_decision": "nothing urgent"}}
        await ctx.assign("urgent_decision", "risk.isabel", "Urgent compliance review",
                         "Review today's urgent proposals (list_initiatives status=proposed) with review_initiative. Be fast and specific about any rule breach.",
                         mock={"biz": "review"})
        t = await ctx.assign("urgent_decision", "exec.priya", "Urgent executive decision",
                             "Decide today's urgent proposals (list_initiatives). Approve only if clearly justified by the data, compliant and affordable (get_budget); use decide_initiative.",
                             mock={"biz": "decide", "max_approvals": 2})
        return {"outputs": {"urgent_decision": t.result or ""}}

    @ctx.step("standup", "Stand-up")
    async def standup(state: FlowState):
        t = await ctx.assign("standup", "exec.mei", f"Stand-up note {_today(ctx)}",
                             "Write the daily stand-up note (write_note kind='standup', under 600 characters): today's top priorities, who owns them, and any decision the CEO made today. "
                             "Use get_alerts and list_initiatives to ground it.", mock={"biz": "standup"})
        return {"outputs": {"standup": t.result or ""}}

    g = StateGraph(FlowState)
    for fn in (data_brief, triage, investigate, urgent_decision, standup):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "data_brief")
    g.add_edge("data_brief", "triage")
    g.add_conditional_edges("triage", route, ["investigate", "urgent_decision"])
    g.add_edge("investigate", "urgent_decision")
    g.add_edge("urgent_decision", "standup")
    g.add_edge("standup", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== weekly
def build_weekly(ctx: Ctx):
    P = ctx.run.params
    week = int(P.get("week", 0))

    @ctx.step("week_brief", "Weekly business review")
    async def week_brief(state: FlowState):
        t = await ctx.assign("week_brief", "data.arjun", f"Weekly review, week of {_today(ctx)}",
                             "Prepare the weekly business review: 28-day KPIs vs targets, what changed vs the previous period, and how running initiatives are performing "
                             "(evaluate_initiative). " + TOOLS_HINT + " Write it with write_note kind='daily_brief' titled 'Weekly review' (under 1000 characters).",
                             mock={"biz": "brief"})
        return {"outputs": {"week_brief": t.result or ""}}

    def make_proposer(dept: str):
        @ctx.step(f"propose_{dept}", f"{dept} proposals")
        async def propose(state: FlowState):
            lead = dept_lead(dept)
            t = await ctx.assign(f"propose_{dept}", lead.id, f"{dept}: weekly proposals",
                                 f"You are the head of your department. Review your function's metrics ({TOOLS_HINT}) and, ONLY where the evidence justifies it, "
                                 "propose up to 2 initiatives with propose_initiative. First call describe_initiative_kinds to get exact parameters, check list_initiatives (do not duplicate), "
                                 "get_budget and unit_economics. Every proposal needs a rationale citing numbers and an expected effect. If nothing is needed, say so and propose nothing.",
                                 mock={"biz": "propose", "dept": dept, "week": week})
            return {"outputs": {f"propose_{dept}": t.result or ""}}
        propose.__name__ = f"propose_{dept}"
        return propose

    @ctx.step("challenge_risk", "Compliance challenge")
    async def challenge_risk(state: FlowState):
        t = await ctx.assign("challenge_risk", "risk.isabel", "Compliance review of proposals",
                             "Review every proposed initiative (list_initiatives status=proposed) against community rating, the premium-round rule, Privacy Act, ASIC and hospital-tier rules. "
                             "If a proposal is unclear, ask its proposer with consult_peer first. Record each view with review_initiative (endorse / concerns / object). Objections are binding.",
                             mock={"biz": "review"})
        return {"outputs": {"challenge_risk": t.result or ""}}

    @ctx.step("challenge_finance", "Financial challenge")
    async def challenge_finance(state: FlowState):
        t = await ctx.assign("challenge_finance", "exec.daniel", "Financial review of proposals",
                             "Review every proposed initiative (list_initiatives status=proposed) as CFO: cost vs get_budget, payback using unit_economics, effect on the loss ratio and margin. "
                             "Challenge weak cases by asking the proposer with consult_peer. Record each view with review_initiative.",
                             mock={"biz": "review"})
        return {"outputs": {"challenge_finance": t.result or ""}}

    @ctx.step("decide", "CEO decision")
    async def decide(state: FlowState):
        t = await ctx.assign("decide", "exec.priya", "Weekly strategy decisions",
                             "As CEO decide every open proposal (list_initiatives with status in_review and proposed). Weigh the data (get_alerts, get_kpis), the Risk and Finance reviews, "
                             f"and the budget (get_budget). Approve at most {int(P.get('max_approvals', 3))} this week, favouring the biggest gap to target per dollar. "
                             "Reject with a clear reason otherwise. Use decide_initiative for each.",
                             mock={"biz": "decide", "max_approvals": int(P.get("max_approvals", 3))})
        return {"outputs": {"decide": t.result or ""}}

    @ctx.step("communicate", "Communicate the plan")
    async def communicate(state: FlowState):
        t = await ctx.assign("communicate", "exec.mei", "Communicate the weekly plan",
                             "Write the weekly plan note (write_note kind='weekly_plan', under 900 characters): what was approved (list_initiatives status=approved), owners, budget left (get_budget), what was declined and why.",
                             mock={"biz": "plan_note"})
        if P.get("use_meetings"):
            await ctx.present_round("brd", ["exec.priya", "exec.daniel", "exec.mei", "sales.leo", "claims.helen"], "Weekly strategy decisions")
        return {"outputs": {"communicate": t.result or ""}}

    g = StateGraph(FlowState)
    proposers = [make_proposer(d) for d in PROPOSERS]
    for fn in (week_brief, challenge_risk, challenge_finance, decide, communicate, *proposers):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "week_brief")
    for d in PROPOSERS:
        g.add_edge("week_brief", f"propose_{d}")
    g.add_edge([f"propose_{d}" for d in PROPOSERS], "challenge_risk")
    g.add_edge([f"propose_{d}" for d in PROPOSERS], "challenge_finance")
    g.add_edge(["challenge_risk", "challenge_finance"], "decide")
    g.add_edge("decide", "communicate")
    g.add_edge("communicate", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== monthly
def build_monthly(ctx: Ctx):
    P = ctx.run.params

    @ctx.step("evaluate", "Evaluate initiatives")
    async def evaluate(state: FlowState):
        t = await ctx.assign("evaluate", "data.arjun", "Evaluate running and completed initiatives",
                             "Evaluate every running or recently completed initiative with evaluate_initiative (before/after adjusted for last year's seasonality) and compare with what was expected. "
                             "Write kind='lesson' note: what worked, what did not, what to do differently (under 1000 characters). Be honest about uncertainty.",
                             mock={"biz": "evaluate"})
        return {"outputs": {"evaluate": t.result or ""}}

    @ctx.step("board_summary", "Board summary")
    async def board_summary(state: FlowState):
        t = await ctx.assign("board_summary", "exec.daniel", "Monthly board summary",
                             "Write the monthly board summary (write_note kind='board_note', under 1000 characters): 28-day results vs targets (get_kpis), margin and loss ratio, strategy budget (get_budget), "
                             "the main risks and next month's priorities.", mock={"biz": "board_note"})
        if P.get("use_meetings"):
            await ctx.present_round("brd", ["exec.priya", "exec.daniel", "data.arjun", "risk.isabel", "people.camille"], "Monthly board review")
        return {"outputs": {"board_summary": t.result or ""}}

    g = StateGraph(FlowState)
    g.add_node("evaluate", evaluate)
    g.add_node("board_summary", board_summary)
    g.add_edge(START, "evaluate")
    g.add_edge("evaluate", "board_summary")
    g.add_edge("board_summary", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== annual premium round
def build_premium_round(ctx: Ctx):
    @ctx.step("analyse", "Actuarial analysis")
    async def analyse(state: FlowState):
        t = await ctx.assign("analyse", "data.yuki", "Premium round: actuarial view",
                             "Analyse the annual premium round (effective 1 April). Use premium_round_info (the approved industry cap), get_kpis (loss ratio, trend), get_breakdown "
                             "(claims by type), get_products (price vs market, cancellations). Recommend a range per plan family; higher where claims ratios are high, lower where price-sensitive. Note the cancellation risk. "
                             "Write kind='premium_analysis'.", mock={"biz": "premium_analyse"})
        return {"outputs": {"analyse": t.result or ""}}

    @ctx.step("propose_round", "Pricing proposal")
    async def propose_round(state: FlowState):
        t = await ctx.assign("propose_round", "prod.elena", "Premium round: pricing proposal",
                             "Using the actuarial note and premium_round_info, propose the price change per plan as fractions (e.g. 0.034 = +3.4%). The weighted average must stay at or under the approved industry cap and no plan may exceed it by more than 2 points. "
                             "Write it with write_note kind='premium_proposal' and end your answer with the JSON object of plan id to fraction.",
                             mock={"biz": "premium_propose"})
        return {"outputs": {"propose_round": t.result or ""}}

    @ctx.step("compliance", "Compliance check")
    async def compliance(state: FlowState):
        t = await ctx.assign("compliance", "risk.kwame", "Premium round: regulatory check",
                             "Check the pricing proposal against the premium-round rules (premium_round_info): only effective 1 April, weighted average under the approved cap, no health-status-based differences, "
                             "plus the Ombudsman and ACCC risk of price shocks. Reply with a clear PASS or FAIL and conditions.",
                             mock={})
        return {"outputs": {"compliance": t.result or ""}}

    @ctx.step("decide_round", "Decide the round")
    async def decide_round(state: FlowState):
        o = state.get("outputs", {})
        t = await ctx.assign("decide_round", "exec.daniel", "Premium round: decision",
                             "Decide the premium round with submit_premium_round (JSON plan id -> fraction). Start from the proposal and the compliance view below; you may adjust. "
                             f"Proposal: {o.get('propose_round', '')[:900]} Compliance: {o.get('compliance', '')[:400]}",
                             mock={"biz": "premium_decide"}, context={"proposal": o.get("propose_round", ""), "compliance": o.get("compliance", "")})
        return {"outputs": {"decide_round": t.result or ""}}

    @ctx.step("member_comms", "Member communications")
    async def member_comms(state: FlowState):
        a = await ctx.assign("member_comms", "care.rafael", "Prepare for premium-notice call volumes",
                             "The premium round notices go out soon. Plan call-centre readiness (roster, scripts, self-service) using get_kpis and get_team_status.", mock={})
        b = await ctx.assign("member_comms", "mkt.ben", "Premium notice retention messaging",
                             "Plan transparent, non-misleading member messaging about the price change and the retention offers available.", mock={})
        return {"outputs": {"member_comms": f"{a.result or ''} | {b.result or ''}"}}

    g = StateGraph(FlowState)
    for fn in (analyse, propose_round, compliance, decide_round, member_comms):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "analyse")
    g.add_edge("analyse", "propose_round")
    g.add_edge("propose_round", "compliance")
    g.add_edge("compliance", "decide_round")
    g.add_edge("decide_round", "member_comms")
    g.add_edge("member_comms", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== team health
def build_team_health(ctx: Ctx):
    @ctx.step("survey", "Engagement review")
    async def survey(state: FlowState):
        t = await ctx.assign("survey", "people.zara", "Monthly engagement and capacity review",
                             "Review the whole workforce with get_team_status: utilisation (over 100% is a burnout risk), engagement (target 70), annualised attrition, open roles and starters still ramping. "
                             "Write kind='people_note' summarising hotspots by department.", mock={})
        return {"outputs": {"survey": t.result or ""}}

    @ctx.step("people_plan", "People plan")
    async def people_plan(state: FlowState):
        t = await ctx.assign("people_plan", "people.camille", "Workforce plan proposals",
                             "From the engagement review, propose up to 2 people initiatives (hire / training / wellbeing_program) with propose_initiative where the data justifies them. "
                             "Check get_budget and list_initiatives first; do not duplicate.", mock={"biz": "propose", "dept": "people", "week": 0})
        return {"outputs": {"people_plan": t.result or ""}}

    @ctx.step("finance_review", "Cost review")
    async def finance_review(state: FlowState):
        t = await ctx.assign("finance_review", "exec.daniel", "Cost review of people proposals",
                             "Review the proposed people initiatives (list_initiatives status=proposed) for cost and payback, with review_initiative.", mock={"biz": "review"})
        return {"outputs": {"finance_review": t.result or ""}}

    @ctx.step("people_decide", "Decide")
    async def people_decide(state: FlowState):
        t = await ctx.assign("people_decide", "exec.priya", "Decide the people plan",
                             "Decide the open people proposals with decide_initiative; weigh the data, the CFO's view and the budget.", mock={"biz": "decide", "max_approvals": 2})
        return {"outputs": {"people_decide": t.result or ""}}

    g = StateGraph(FlowState)
    for fn in (survey, people_plan, finance_review, people_decide):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "survey")
    g.add_edge("survey", "people_plan")
    g.add_edge("people_plan", "finance_review")
    g.add_edge("finance_review", "people_decide")
    g.add_edge("people_decide", END)
    return g.compile(checkpointer=InMemorySaver())


DAILY_OPS = {"name": "daily_ops", "title": "Daily operations review", "description": "Brief → triage → investigate each alert in parallel → urgent decisions → stand-up.",
             "params": {"max_investigations": "int (default 2)", "cooldown_days": "int (default 5)"}, "build": build_daily}
WEEKLY_STRATEGY = {"name": "weekly_strategy", "title": "Weekly strategy cycle", "description": "Departments propose, Risk and Finance challenge, the CEO decides.",
                   "params": {"max_approvals": "int (default 3)", "use_meetings": "bool", "week": "int"}, "build": build_weekly}
MONTHLY_REVIEW = {"name": "monthly_review", "title": "Monthly review", "description": "Evaluate initiatives, write the board summary.",
                  "params": {"use_meetings": "bool"}, "build": build_monthly}
PREMIUM_ROUND = {"name": "premium_round", "title": "Annual premium round", "description": "Actuarial view, pricing proposal, compliance, CEO/CFO decision, member communications.",
                 "params": {}, "build": build_premium_round}
TEAM_HEALTH = {"name": "team_health", "title": "Team health review", "description": "Engagement and capacity review, people plan, cost review, decision.",
               "params": {}, "build": build_team_health}
