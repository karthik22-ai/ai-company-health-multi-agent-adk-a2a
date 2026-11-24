"""Plan → act → reflect (LangGraph).

  weekly_goals   Mondays   reflect on last week's goals (met / missed, what we tried) → lessons into the leaders' memories and a
                           "Weekly goals review" document → the CEO sets this week's measurable goals (rule-based goals if none are set)
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from hq.agents.roster import AGENTS, dept_lead
from hq.quality.goals import week_of
from hq.workflows.base import Ctx


class S(TypedDict, total=False):
    params: dict[str, Any]
    outputs: dict[str, Any]


def build_weekly_goals(ctx: Ctx):
    co, w = ctx.svc.company, ctx.world
    ceo = dept_lead("exec").id

    @ctx.step("reflect", "Review last week's goals and learn from them")
    async def reflect(state: S) -> dict:
        last = week_of(co.today - timedelta(days=7))
        if not co.goals.for_week(last) or any(r["week"] == last for r in co.goals.reviews(2)):
            return {"outputs": {"review": None}}
        rev = co.goals.review(last)
        lesson = co.goals.lesson(rev)
        for a in [s.id for s in AGENTS.values() if s.lead or s.dept == "exec"]:
            w.remember(a, "lesson", lesson, .8)
        table = "| Goal | Target | Actual | Result | Owner |\n|---|---|---|---|---|\n" + "\n".join(
            f"| {g['label']} | {g['target']:g} | {g['actual'] if g['actual'] is not None else 'n/a'} | {'met' if g['met'] else 'missed'} | {g['owner']} |"
            for g in rev["goals"])
        tried = "\n".join(f"- {t}" for t in rev["initiatives"] + rev["campaigns"]) or "- No new initiatives or campaigns."
        f = co.files.create("report", f"Weekly goals review {last}", ceo,
                            {"markdown": f"# Weekly goals review {last}\n\n{lesson}\n\n## Goals\n\n{table}\n\n## What we tried\n\n{tried}\n", "charts": []},
                            summary=lesson[:300])
        w.work_file(f)
        w.log(f"🎯 {lesson[:180]}")
        return {"outputs": {"review": last, "file": f["id"]}}

    @ctx.step("plan", "The CEO sets this week's goals")
    async def plan(state: S) -> dict:
        week = week_of(co.today)
        await ctx.assign("plan", ceo, f"Goals for {week}",
                         "Plan the week. Read get_weekly_goals (last reviews: what was met or missed and what we tried), get_membership_funnel and "
                         "get_kpis. Then set 3-4 measurable goals for this week with set_weekly_goals, each with an owner and a short reason. "
                         "Learn from the reviews: keep what worked, change what didn't.", mock={"biz": "weekly_goals"})
        if not co.goals.for_week(week):
            co.goals.set("system", co.goals.defaults(week), week)
        goals = co.goals.for_week(week)
        for a in [s.id for s in AGENTS.values() if s.lead or s.dept == "exec"]:
            w.remember(a, "goal", f"Company goals for {week}: " + "; ".join(f"{g['label']} {g['target']:g} (owner {g['owner']})" for g in goals), .7)
        return {"outputs": {"week": week, "goals": [g["metric"] for g in goals]}}

    g = StateGraph(S)
    g.add_node("reflect", reflect)
    g.add_node("plan", plan)
    g.add_edge(START, "reflect")
    g.add_edge("reflect", "plan")
    g.add_edge("plan", END)
    return g.compile(checkpointer=InMemorySaver())


WEEKLY_GOALS = {"name": "weekly_goals", "title": "Weekly goals", "description": "Reflect on last week's goals, then set this week's.",
                "params": {}, "build": build_weekly_goals}
