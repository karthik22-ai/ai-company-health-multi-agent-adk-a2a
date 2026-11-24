"""Workflows for the teams' real work products (LangGraph).

  meeting          on request (you)     attendees walk in → each prepares a deck from real data on YOUR agenda (in parallel)
                                        → each presents on the room screen → minutes → back to desks; decks + minutes are downloadable
  reporting_cycle  Fridays              Reporting & Insights: company dashboard + a department dashboard + the weekly report
  it_build         Tuesdays             IT & Apps works its app backlog: growth and off-target signals raise requests, the Head of IT
                                        ranks every request by impact, a developer builds the top one and the team that asked is told
  access_review    when requested       the Data team reviews data access requests (least privilege)
  hiring           when a hire is approved  People & Culture hires a new AI agent into the team that needs it
  work_request     on request (you)     ask any department for a dashboard, app, report, hire or analysis
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from hq.agents.roster import AGENTS, DEPARTMENTS, MEETING_ROOMS, dept_lead
from hq.workflows.base import Ctx, merge_dict  # noqa: F401  (merge_dict kept for symmetry with biz_flows)

DATA_HINT = ("Use real numbers from your tools (get_kpis, get_breakdown, query_data, get_team_status, list_initiatives, list_work_files). "
             "If query_data says access is denied, either use a dataset you can read or ask with request_data_access. "
             "If your team keeps needing a tracker, monitor or tool that doesn't exist, ask IT to build it with request_app.")


class S(TypedDict, total=False):
    params: dict[str, Any]
    outputs: dict[str, Any]


def _compact_chart(ch: dict[str, Any] | None) -> dict[str, Any] | None:
    """A chart small enough to send to the 3D UI for the meeting room screen."""
    if not ch or not ch.get("rows") or ch.get("type") == "table":
        return None
    cols, rows = ch["columns"], ch["rows"][-60:]
    xi = cols.index(ch["x"]) if ch.get("x") in cols else 0
    series = []
    for y in [y for y in ch.get("y", []) if y in cols][:3]:
        yi = cols.index(y)
        series.append({"name": y, "values": [float(r[yi]) if isinstance(r[yi], (int, float)) else 0.0 for r in rows]})
    return {"title": ch.get("title", ""), "type": ch.get("type", "line"), "labels": [str(r[xi]) for r in rows], "series": series}


def ui_slides(deck: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for s in deck["content"].get("slides", []):
        out.append({"title": s.get("title", ""), "bullets": s.get("bullets", [])[:5], "chart": _compact_chart(s.get("chart")), "file": deck["id"]})
    return out


# =============================================================================== meeting with an agenda
def build_meeting(ctx: Ctx):
    P = ctx.run.params
    w, files = ctx.world, ctx.svc.company.files
    room = P.get("room") if P.get("room") in MEETING_ROOMS else ctx.free_room()
    attendees = [a for a in P.get("attendees", []) if a in AGENTS][:8] or [dept_lead("exec").id]
    agenda = str(P.get("agenda") or "Status update").strip()[:600]
    mid = f"M-{ctx.run.id}"
    organizer = P.get("organizer") if P.get("organizer") in AGENTS else ("exec.mei" if "exec.mei" in AGENTS else attendees[0])

    @ctx.step("assemble", "Attendees walk to the meeting room")
    async def assemble(state: S):
        w.meeting(room, attendees, agenda[:80], meeting_id=mid, agenda=agenda, organizer=organizer)
        for a in attendees:
            w.set_status(a, "meeting", f"Meeting: {agenda[:50]}")
        w.emit({"type": "meeting_started", "meeting": mid, "room": room, "agenda": agenda, "attendees": attendees})
        await ctx.pause(8)
        return {}

    @ctx.step("prepare", "Everyone prepares a deck on the agenda")
    async def prepare(state: S):
        async def one(a: str) -> None:
            spec = AGENTS[a]
            await ctx.assign("prepare", a, f"Prepare: {agenda[:60]}",
                             f"You are in a meeting called by the CEO (the user). Agenda: {agenda}\n"
                             f"Prepare 2-4 slides that answer the agenda from the point of view of your role ({spec.role}, {DEPARTMENTS[spec.dept].name}). "
                             f"{DATA_HINT} Add a chart (a SQL query you can run) where a trend or comparison helps. "
                             f"Then call create_presentation(title, slides_json, agenda, meeting_id='{mid}') exactly once. Finish with one sentence summarising your message.",
                             mock={"biz": "presentation", "meeting_id": mid, "agenda": agenda}, context={"meeting_id": mid, "agenda": agenda})
            w.set_status(a, "meeting", f"Meeting: {agenda[:50]}")
        await asyncio.gather(*[one(a) for a in attendees])
        return {}

    @ctx.step("present", "Presentations on the room screen")
    async def present(state: S):
        decks = []
        for a in attendees:
            deck = next(iter(files.list(author=a, kind="presentation", meeting=mid, limit=1)), None)
            if deck:
                full = files.get(deck["id"])
                slides = ui_slides(full)
                decks.append({"agent": a, "file": deck["id"], "title": deck["title"], "slides": [{"title": s["title"], "bullets": s["bullets"]} for s in slides]})
            else:
                slides = await ctx.runtime.slides(a)
            w.present(a, slides)
            await ctx.pause(9 * max(1, len(slides)) + 4)
        return {"outputs": {"decks": decks}}

    @ctx.step("minutes", "Minutes and actions")
    async def minutes(state: S):
        decks = state.get("outputs", {}).get("decks", [])
        digest = "\n".join(f"- {AGENTS[d['agent']].name} ({d['file']}): " + " | ".join(f"{s['title']}: {'; '.join(s['bullets'][:3])}" for s in d["slides"]) for d in decks)
        t = await ctx.assign("minutes", organizer, f"Minutes: {agenda[:60]}",
                             f"Write the minutes of the meeting. Agenda: {agenda}\nWhat each person presented:\n{digest or '(no decks)'}\n"
                             "Call create_report(title, markdown, kind='minutes') with: attendees, key points per presenter (with their numbers), decisions, "
                             "action items with an owner each. Keep it under 500 words.",
                             mock={"biz": "minutes", "digest": digest, "agenda": agenda})
        mins = next(iter(files.list(author=organizer, kind="minutes", limit=1)), None)
        if mins:
            files.store.db.execute("UPDATE files SET meeting=? WHERE id=?", (mid, mins["id"]))
            files.store.commit()
        return {"outputs": {"minutes": mins["id"] if mins else None, "summary": t.result or ""}}

    @ctx.step("close", "Back to desks")
    async def close(state: S):
        w.end_meeting(room)
        for a in attendees:
            w.set_status(a, "idle", "Back at desk")
        out = files.list(meeting=mid, limit=20)
        done = {"meeting": mid, "room": room, "agenda": agenda, "files": out, "date": ctx.svc.company.today.isoformat(), "attendees": attendees}
        hist = files.store.get_kv("meetings", [])
        files.store.set_kv("meetings", (hist + [{k: v for k, v in done.items() if k != "files"}])[-60:])
        w.emit({"type": "meeting_done", **done})
        return {"outputs": {"meeting": mid, "files": [f["id"] for f in out]}}

    g = StateGraph(S)
    for n, fn in (("assemble", assemble), ("prepare", prepare), ("present", present), ("minutes", minutes), ("close", close)):
        g.add_node(n, fn)
    g.add_edge(START, "assemble")
    g.add_edge("assemble", "prepare")
    g.add_edge("prepare", "present")
    g.add_edge("present", "minutes")
    g.add_edge("minutes", "close")
    g.add_edge("close", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== Reporting & Insights weekly cycle
DEPT_DASH = [("sales", "Sales & conversion"), ("claims", "Claims operations"), ("care", "Member care service"), ("mkt", "Marketing & leads"),
             ("people", "Workforce & engagement"), ("prod", "Plans & pricing")]


def build_reporting(ctx: Ctx):
    week = int(ctx.run.params.get("week") or 0)
    dept, topic = DEPT_DASH[week % len(DEPT_DASH)]

    def ag(pref: str) -> str:
        return pref if pref in AGENTS else dept_lead("bi").id

    @ctx.step("build", "Dashboards and the weekly report")
    async def build(state: S):
        jobs = [
            ctx.assign("build", ag("bi.ravi"), "Company performance dashboard",
                       "Build the executive 'Company performance' dashboard with create_dashboard: 4-6 charts from daily_kpi over the last 60-90 days "
                       "(new sales, cancellations, net adds, loss ratio, margin, claims SLA or call wait) plus 3-5 headline KPI tiles with current values vs target "
                       "(get_kpis). Write a description saying what the executives should watch.", mock={"biz": "dashboard", "topic": "company"}),
            ctx.assign("build", ag("bi.diego"), f"{topic} dashboard",
                       f"Build a '{topic}' dashboard for the {DEPARTMENTS[dept].name} team with create_dashboard (3-5 charts). Use the most relevant tables "
                       f"(breakdowns by state, channel, plan, reason or type). If a table is denied, request access with request_data_access and use what you can read.",
                       mock={"biz": "dashboard", "topic": dept}),
            ctx.assign("build", ag("bi.emma"), "Weekly performance report",
                       f"Write the weekly performance report with create_report: headline results vs targets, what changed and why (cite breakdowns), initiatives "
                       f"running and early results, risks for next week. Include 1-2 charts. {DATA_HINT}", mock={"biz": "report", "topic": "weekly"}),
        ]
        await asyncio.gather(*jobs)
        return {}

    g = StateGraph(S)
    g.add_node("build", build)
    g.add_edge(START, "build")
    g.add_edge("build", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== IT & Apps monthly build
APPS = [("Plan & price explorer", "Product & Pricing and Sales: browse every plan, its price, members and recent sales; filter by category.",
         {"plans": "SELECT id, name, category, tier, monthly_price, active FROM products",
          "sales_by_plan": "SELECT product_id, SUM(sales) AS sales_90d FROM daily_sales WHERE date >= date((SELECT MAX(date) FROM daily_sales), '-90 day') GROUP BY product_id"}),
        ("Claims backlog tracker", "Claims: daily arrivals, processed, backlog and SLA for the last 90 days with a target line.",
         {"claims_ops": "SELECT date, claims_arrivals, claims_processed, claims_backlog, claims_sla_pct FROM daily_kpi ORDER BY date DESC LIMIT 90"}),
        ("Sales channel explorer", "Sales & Marketing: sales by channel and state over the last 8 weeks, sortable.",
         {"by_channel": "SELECT channel, state, SUM(sales) AS sales FROM daily_sales WHERE date >= date((SELECT MAX(date) FROM daily_sales), '-56 day') GROUP BY channel, state"}),
        ("Contact centre monitor", "Member Care: calls, answered, average wait and abandon rate for the last 60 days.",
         {"calls": "SELECT date, calls, calls_answered, avg_wait_s, abandon_pct, csat FROM daily_kpi ORDER BY date DESC LIMIT 60"})]


def build_it(ctx: Ctx):
    P = ctx.run.params
    co = ctx.svc.company
    ar = co.app_requests

    @ctx.step("signals", "The company's numbers raise app requests")
    async def signals(state: S):
        raised = ar.scan_signals()
        if P.get("request"):                                   # the CEO asked IT directly
            res = ar.add(str(P.get("requester") or "exec.priya"), str(P.get("title") or P["request"])[:80], str(P["request"]),
                         source="ceo", impact="requested by the CEO")
            if res.get("request_id"):
                ar.prioritise("ceo", [{"id": res["request_id"], "decision": "build", "note": "CEO request"}])
                ar.update(res["request_id"], priority=999)
        for r in raised:
            ctx.svc.world.log(f"🧩 App request raised by the numbers ({r['signal']}): {r['title']}")
        return {"outputs": {"raised": raised}}

    @ctx.step("rank", "Head of IT ranks the app backlog")
    async def rank(state: S):
        waiting = ar.list(("open",))
        if not waiting:
            return {}
        head = dept_lead("it").id
        await ctx.assign("rank", head, "Rank the app backlog",
                         "Review IT's app backlog with get_app_backlog. For each open request decide build / later / decline and rank them by business "
                         "impact (members, money, service levels, how many people it helps, and whether it is blocking a team). Prefer requests backed by "
                         "the company's numbers or the CEO. Call prioritise_app_requests with your ranking and a one-line summary.",
                         mock={"biz": "it_backlog"})
        return {}

    @ctx.step("build_app", "Build the top app")
    async def build_app(state: S):
        req = ar.next_to_build()
        if req is None:                                        # nothing requested: build a useful standard app not built yet
            built = {f["title"].lower() for f in co.files.list(kind="app")}
            spare = [a for a in APPS if a[0].lower() not in built]
            if not spare:
                return {}
            title, need, queries = spare[int(P.get("n") or 0) % len(spare)]
            res = ar.add(dept_lead("it").id, title, need, json.dumps(queries), "standard internal app", source="agent")
            req = ar.get(res["request_id"])
        ar.update(req["id"], status="building")
        dev = next((a for a in ("it.fatima", "it.aisha") if a in AGENTS), dept_lead("it").id)
        who = AGENTS[req["requester"]].name if req["requester"] in AGENTS else "the CEO"
        try:
            queries = json.loads(req["data_needed"]) if req["data_needed"].strip().startswith("{") else {}
        except ValueError:
            queries = {}
        brief = (f"App request #{req['id']} from {who} ({req['dept']}): {req['title']}\nUse case: {req['use_case']}\n"
                 + (f"Data they need: {req['data_needed']}\n" if req["data_needed"] else "")
                 + (f"Why it matters: {req['impact']}\n" if req["impact"] else ""))
        await ctx.assign("build_app", dev, f"App: {req['title'][:50]}",
                         f"{brief}Build it. Check the data with query_data / list_datasets first. Call create_app(title, description, html, data_queries_json, "
                         f"request_id={req['id']}). The HTML must be one self-contained page: a clean dark UI, a header, filters or sorting where useful, "
                         "a table and at least one chart drawn on <canvas> from window.HQ_DATA. No external scripts, no fetch.",
                         mock={"biz": "app", "title": req["title"], "queries": queries or None, "request": req["use_case"], "request_id": req["id"]})
        if (ar.get(req["id"]) or {}).get("status") == "building":     # not delivered: back on the plan for next week
            ar.update(req["id"], status="planned")
        return {}

    g = StateGraph(S)
    for name, fn in (("signals", signals), ("rank", rank), ("build_app", build_app)):
        g.add_node(name, fn)
    g.add_edge(START, "signals")
    g.add_edge("signals", "rank")
    g.add_edge("rank", "build_app")
    g.add_edge("build_app", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== Data team: access reviews
def build_access(ctx: Ctx):
    @ctx.step("review", "Data team reviews access requests")
    async def review(state: S):
        files = ctx.svc.company.files
        pend = files.access_requests("pending")
        if not pend:
            return {}
        reviewer = "data.chloe" if "data.chloe" in AGENTS else dept_lead("data").id
        lst = "\n".join(f"- #{r['id']}: {r['requester']} wants {r['dataset']} ({r['sensitivity']}): {r['reason']}" for r in pend)
        await ctx.assign("review", reviewer, f"Review {len(pend)} data access request(s)",
                         f"You run data access governance. Pending requests:\n{lst}\nFor each, decide with review_access_request(request_id, decision, note): "
                         "approve when the requester's role genuinely needs it (least privilege); restricted data (claims, HR) needs a clear business reason; "
                         "reject otherwise and say what they can use instead.", mock={"biz": "access_review"})
        return {}

    g = StateGraph(S)
    g.add_node("review", review)
    g.add_edge(START, "review")
    g.add_edge("review", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== People & Culture: hire AI agents for approved hires
def pending_hires(company: Any) -> list[dict[str, Any]]:
    done = set(company.store.get_kv("ai_hired_for", []))
    return [i for i in company.sim.initiatives.values() if i.get("kind") == "hire" and i.get("status") in ("approved", "running") and i["id"] not in done]


def build_hiring(ctx: Ctx):
    @ctx.step("hire", "People & Culture hires a new AI agent")
    async def hire(state: S):
        co = ctx.svc.company
        req = ctx.run.params.get("request")
        todo = [] if req else pending_hires(co)[:1]
        if not req and not todo:
            return {}
        recruiter = "people.ethan" if "people.ethan" in AGENTS else dept_lead("people").id
        if req:
            brief = f"Hiring request: {req}"
            mock = {"biz": "hire", "dept": ctx.run.params.get("dept") or "data", "role": ctx.run.params.get("role") or "Analyst"}
        else:
            ini = todo[0]
            p = ini.get("params", {})
            brief = (f"Initiative {ini['id']} '{ini['title']}' was approved: hire {p.get('fte', '?')} FTE for {p.get('dept')} ({p.get('role', '')}). "
                     f"Rationale: {ini.get('rationale', '')[:300]}")
            mock = {"biz": "hire", "dept": p.get("dept", "claims"), "role": (p.get("role") or "Operations Specialist")}
        await ctx.assign("hire", recruiter, "Hire a new AI agent",
                         f"{brief}\nCreate ONE new AI agent who fills this requirement with hire_agent(dept, name, role, reason): pick a realistic, diverse name, a job "
                         "title that matches the gap, and a reason citing the data or the initiative. Check get_team_status first.", mock=mock)
        if todo:
            co.store.set_kv("ai_hired_for", list(set(co.store.get_kv("ai_hired_for", [])) | {todo[0]["id"]}))
        return {}

    g = StateGraph(S)
    g.add_node("hire", hire)
    g.add_edge(START, "hire")
    g.add_edge("hire", END)
    return g.compile(checkpointer=InMemorySaver())


# =============================================================================== on-demand request to a department
MODE_FOR_DEPT = {"bi": "dashboard", "it": "app", "people": "hire", "data": "access_review"}


def build_request(ctx: Ctx):
    P = ctx.run.params

    @ctx.step("deliver", "Department delivers your request")
    async def deliver(state: S):
        dept = P.get("dept") if P.get("dept") in DEPARTMENTS else "bi"
        agent = P.get("agent") if P.get("agent") in AGENTS else dept_lead(dept).id
        text = str(P.get("text") or "")[:800]
        if dept == "it" and len(text) >= 20:                 # app requests land on IT's backlog so they are tracked and ranked
            res = ctx.svc.company.app_requests.add("exec.priya", text[:80], text, source="ceo", impact="requested by the CEO")
            if res.get("request_id"):
                text += f"\n(This is app request #{res['request_id']}: pass request_id={res['request_id']} to create_app.)"
        t = await ctx.assign("deliver", agent, f"Request: {text[:60]}",
                             f"Request from the CEO (the user): {text}\nDeliver it with your tools and stay within your role: dashboards (create_dashboard), apps "
                             "(create_app), new team members (hire_agent), reports (create_report), data access (review_access_request / request_data_access), "
                             f"or analysis with a written report. You may hand off to a colleague (hand_off_work) if they are better placed. {DATA_HINT} "
                             "Finish with what you delivered and the file id(s).",
                             mock={"biz": MODE_FOR_DEPT.get(dept, "report"), "topic": dept, "request": text})
        return {"outputs": {"result": t.result or ""}}

    g = StateGraph(S)
    g.add_node("deliver", deliver)
    g.add_edge(START, "deliver")
    g.add_edge("deliver", END)
    return g.compile(checkpointer=InMemorySaver())


MEETING = {"name": "meeting", "title": "Meeting", "description": "Agents come to a meeting room, present decks on your agenda, minutes are written.",
           "params": {"room": "str", "agenda": "str", "attendees": "list", "organizer": "str"}, "build": build_meeting}
REPORTING = {"name": "reporting_cycle", "title": "Weekly reporting", "description": "Reporting & Insights publishes dashboards and the weekly report.",
             "params": {"week": "int"}, "build": build_reporting}
IT_BUILD = {"name": "it_build", "title": "IT app backlog", "description": "IT & Apps ranks its app backlog (requests from teams, the numbers and the CEO) "
            "and builds the most important app on the live data.", "params": {"n": "int", "request": "str", "title": "str"}, "build": build_it}
ACCESS_REVIEW = {"name": "access_review", "title": "Data access review", "description": "The Data team reviews pending data access requests.",
                 "params": {}, "build": build_access}
HIRING = {"name": "hiring", "title": "Hiring", "description": "People & Culture hires a new AI agent for an approved hire or a request.",
          "params": {"request": "str", "dept": "str", "role": "str"}, "build": build_hiring}
WORK_REQUEST = {"name": "work_request", "title": "Request", "description": "Ask a department to deliver a dashboard, app, report, hire or analysis.",
                "params": {"dept": "str", "agent": "str", "text": "str"}, "build": build_request}


# =============================================================================== the town: residents shop, Marketing reaches them
def build_town_day(ctx: Ctx):
    @ctx.step("shop", "Town residents review their health cover")
    async def shop(state: S):
        co = ctx.svc.company
        limit = int(ctx.run.params.get("limit") or ctx.svc.settings.town_shoppers_per_day)
        trig = co.town.triggers(co.today, limit)
        if ctx.run.params.get("residents"):                                   # explicit list (tests / you)
            trig = [{"resident": r, "reason": ctx.run.params.get("reason", "You are reviewing your health insurance.")} for r in ctx.run.params["residents"]]
        ctx.world.emit({"type": "town_shoppers", "shoppers": trig})
        for t in trig:
            ctx.world.log(f"🏘 {co.town.resident(t['resident'])['name']}: {t['reason']}")
        await asyncio.gather(*[ctx.runtime.run_resident(t["resident"], t["reason"]) for t in trig])
        ctx.world.emit({"type": "town", **co.town.snapshot()})
        return {"outputs": {"shoppers": [t["resident"] for t in trig]}}

    g = StateGraph(S)
    g.add_node("shop", shop)
    g.add_edge(START, "shop")
    g.add_edge("shop", END)
    return g.compile(checkpointer=InMemorySaver())


def build_town_marketing(ctx: Ctx):
    @ctx.step("campaign", "Marketing plans a town campaign")
    async def campaign(state: S):
        who = "mkt.ben" if "mkt.ben" in AGENTS else dept_lead("mkt").id
        await ctx.assign("campaign", who, "Town campaign",
                         "Grow AI Company Health in the town. Read get_town_insights (who has which insurer, why people switched, reviews) and get_products. "
                         "If there is a sensible opportunity, launch ONE campaign with launch_town_campaign: a clear, honest message, an audience by suburb, "
                         "age band or life stage only (never health status), an optional new-joiner offer, and a duration. Explain your reasoning briefly.",
                         mock={"biz": "town_campaign"})
        return {}

    g = StateGraph(S)
    g.add_node("campaign", campaign)
    g.add_edge(START, "campaign")
    g.add_edge("campaign", END)
    return g.compile(checkpointer=InMemorySaver())


TOWN_DAY = {"name": "town_day", "title": "Town day", "description": "Residents with a reason to review their cover decide what to buy.",
            "params": {"limit": "int", "residents": "list", "reason": "str"}, "build": build_town_day}
TOWN_MARKETING = {"name": "town_marketing", "title": "Town marketing", "description": "Marketing reads town insights and may launch a campaign.",
                  "params": {}, "build": build_town_marketing}
