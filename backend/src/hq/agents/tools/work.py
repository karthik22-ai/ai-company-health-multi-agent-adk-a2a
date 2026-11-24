"""Tools for real work products: data access (run by the Data team), reports, dashboards (Reporting), apps (IT),
presentations (everyone, for meetings) and hiring new AI agents (People & Culture).

Every chart is a SQL query over the synthetic company data, executed with the author's data access; the rows are stored
with the file, so dashboards, decks and downloads always show real numbers.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from hq.agents.roster import AGENTS, DEPARTMENTS, MAX_PER_DEPT
from hq.core.world import World

log = logging.getLogger("hq.work_tools")
DASHBOARD_MAKERS = {"data.marco"}            # plus the whole Reporting & Insights team
CHART_HELP = ('charts_json is a JSON list of charts, each {"title":..., "type":"line|bar|table", "sql":"SELECT ...", "x":"<column>", "y":["<column>",...], '
              '"note":"one-line takeaway"}. Example: [{"title":"New sales, last 60 days","type":"line","sql":"SELECT date, new_sales FROM daily_kpi '
              'ORDER BY date DESC LIMIT 60","x":"date","y":["new_sales"]}]. The SQL runs with YOUR data access.')


def _loads(s: str, default: Any) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON: {e}") from e


def make_work_tools(agent_id: str, world: World) -> list[Callable]:
    me = AGENTS[agent_id]
    company = world.company
    files = company.files

    def publish(f: dict[str, Any], verb: str) -> dict[str, Any]:
        world.work_file(f)
        world.say(agent_id, f"{f['icon']} {verb}: {f['title']}"[:130], 4500)
        return {"ok": True, "file_id": f["id"], "title": f["title"], "kind": f["kind"]}

    # ------------------------------------------------------------------ everyone
    async def list_datasets() -> list:
        """The company's datasets (SQL tables), how sensitive each is, and whether YOU can read it (yes / no / requested)."""
        return files.datasets_for(agent_id)

    async def request_data_access(dataset: str, reason: str) -> dict:
        """Ask the Data & Actuarial team for read access to a dataset you need for your work (see list_datasets). reason: what you need it for."""
        res = files.request_access(agent_id, dataset, reason)
        if res.get("request_id"):
            world.say(agent_id, f"🔑 Asked Data for access to {dataset}", 3500)
            world.access_changed()
        return res

    async def request_app(title: str, use_case: str, data_needed: str = "", impact: str = "") -> dict:
        """Ask IT & Apps to build an internal app your team needs (a tracker, monitor, explorer or calculator on the company's data).
        use_case: who will use it and for what decision or daily task; data_needed: the tables/metrics it should show (SQL welcome);
        impact: what improves if you have it (cite numbers). IT ranks every request weekly by impact and tells you when it is live."""
        res = company.app_requests.add(agent_id, title, use_case, data_needed, impact)
        if res.get("request_id") and res.get("status") == "open" and not res.get("note"):
            world.say(agent_id, f"🧩 Asked IT for an app: {title}"[:120], 3500)
            world.remember(agent_id, "work", f"I asked IT for an app: {title} (request {res['request_id']})", .5)
        return res

    async def list_app_requests() -> list:
        """IT's app backlog: every open, planned and recently delivered app request, who asked and why."""
        return [{k: r[k] for k in ("id", "title", "dept", "requester", "source", "status", "priority", "use_case", "impact", "file_id", "note")}
                for r in company.app_requests.list(("open", "planned", "building")) + company.app_requests.list(("done",), 10)]

    async def create_report(title: str, markdown: str, charts_json: str = "", kind: str = "report") -> dict:
        """Publish a written report (or meeting minutes with kind=minutes) as a work file the whole company can open and download.
        markdown: the report in Markdown (headings, bullets, tables). Cite real numbers from your tools. """ + CHART_HELP
        try:
            charts, errors = files.run_charts(agent_id, _loads(charts_json, []))
        except ValueError as e:
            return {"error": f"charts_json {e}"}
        if errors and not charts and charts_json:
            return {"error": "; ".join(errors)}
        f = files.create("minutes" if kind == "minutes" else "report", title, agent_id, {"markdown": markdown[:12000], "charts": charts},
                         summary=markdown.strip().splitlines()[0][:200] if markdown.strip() else "")
        out = publish(f, "Published")
        if errors:
            out["chart_errors"] = errors
        return out

    async def create_presentation(title: str, slides_json: str, agenda: str = "", meeting_id: str = "") -> dict:
        """Create the slide deck you will present in a meeting (it is shown on the meeting room screen and can be downloaded as PowerPoint).
        slides_json: JSON list of 2-5 slides, each {"title":..., "bullets":["...", "..."], "chart": optional chart {"title","type","sql","x","y"}}.
        Put real numbers from your tools in the bullets; add a chart where a trend or comparison helps."""
        try:
            raw = _loads(slides_json, [])
        except ValueError as e:
            return {"error": f"slides_json {e}"}
        if not isinstance(raw, list) or not raw:
            return {"error": "slides_json must be a non-empty JSON list of slides"}
        slides, errors = [], []
        for s in raw[:6]:
            if not isinstance(s, dict):
                continue
            sl = {"title": str(s.get("title", ""))[:90], "bullets": [str(b)[:160] for b in (s.get("bullets") or [])][:6]}
            if isinstance(s.get("chart"), dict):
                ch, err = files.run_charts(agent_id, [s["chart"]])
                if ch:
                    sl["chart"] = ch[0]
                errors += err
            slides.append(sl)
        f = files.create("presentation", title, agent_id, {"slides": slides, "agenda": agenda[:300]}, summary=agenda[:200], meeting=meeting_id or None)
        out = publish(f, "Deck ready")
        out["slides"] = len(slides)
        if errors:
            out["chart_errors"] = errors
        return out

    async def list_work_files(dept: str = "", kind: str = "") -> list:
        """Work files the teams have produced (reports, dashboards, presentations, apps, minutes). Filter by dept id and/or kind."""
        return files.list(dept=dept or None, kind=kind or None, limit=20)

    async def read_work_file(file_id: str) -> dict:
        """Open a work file: its text, slides or chart data (trimmed)."""
        f = files.get(file_id)
        if not f:
            return {"error": "no such file"}
        c = f["content"]
        brief = {k: v for k, v in f.items() if k != "content"}
        brief["markdown"] = (c.get("markdown") or c.get("description") or "")[:2500]
        brief["slides"] = [{"title": s.get("title"), "bullets": s.get("bullets")} for s in c.get("slides", [])]
        brief["charts"] = [{"title": ch["title"], "columns": ch["columns"], "last_rows": ch["rows"][-5:]} for ch in c.get("charts", [])]
        return brief

    async def get_town_insights() -> dict:
        """The town next door (100 residents): who is covered by which insurer, recent buying/switching decisions and their reasons, reviews,
        active campaigns. Aggregate only - never use or ask for anyone's health status (community rating)."""
        return company.town.insights()

    async def get_membership_funnel(days: int = 28) -> dict:
        """How we win and lose members in Wattle Grove: residents reviewing their cover, who called us, who joined us and why, who left and why,
        which funds won instead, our health care use and the levers (offers, perks, deals) live right now."""
        if getattr(company, "economy", None) is None:
            return {"note": "membership funnel is available when the company runs on the town agents"}
        return company.economy.funnel(max(1, min(int(days), 120)))

    tools: list[Callable] = [list_datasets, request_data_access, create_report, create_presentation, list_work_files, read_work_file, get_town_insights,
                             get_membership_funnel, request_app, list_app_requests]

    if me.dept == "mkt":
        async def launch_town_campaign(title: str, message: str, audience_json: str, offer: str = "", weeks: int = 4) -> dict:
            """Launch a marketing campaign in the town. message: what people will see (honest, no misleading claims). audience_json: JSON object with
            optional "suburbs" (list), "age_min", "age_max", "life_stage" (list of single, couple, family, single_parent, retirees, share_house).
            Never target by health status. offer: optional new-joiner offer. weeks: 1-8."""
            try:
                aud = _loads(audience_json, {})
            except ValueError as e:
                return {"error": f"audience_json {e}"}
            res = company.town.launch_campaign(agent_id, title, message, aud if isinstance(aud, dict) else {}, offer, weeks)
            if res.get("ok"):
                world.say(agent_id, f"📣 Town campaign: {title} (reach {res['reach']})"[:130], 5000)
                world.emit({"type": "town_campaign", "campaign": {"title": title, "message": message, "offer": offer, "by": agent_id, "reach": res["reach"], "until": res["until"]}})
            return res
        tools.append(launch_town_campaign)

    # ------------------------------------------------------------------ Data & Actuarial: data access governance
    if me.dept == "data":
        async def list_access_requests() -> list:
            """Pending data access requests waiting for the Data team's decision."""
            return files.access_requests("pending")

        async def review_access_request(request_id: int, decision: str, note: str) -> dict:
            """Approve or reject a data access request. decision: approve or reject. Grant only what the requester's role needs (least privilege);
            restricted data (claims, HR) needs a clear business reason. note: one sentence explaining the decision."""
            if decision not in ("approve", "reject"):
                return {"error": "decision must be approve or reject"}
            res = files.review_access(int(request_id), agent_id, decision == "approve", note)
            if res.get("ok"):
                world.say(agent_id, f"{'🔓 Granted' if decision == 'approve' else '🔒 Declined'} {res['dataset']} → {res['requester']}", 4000)
                world.say(res["requester"], f"{'🔓 Access to ' + res['dataset'] + ' granted' if decision == 'approve' else '🔒 Access request declined'}", 3500)
                world.access_changed()
            return res

        async def revoke_data_access(grant_id: int, reason: str) -> dict:
            """Revoke an access grant that is no longer needed."""
            res = files.revoke(int(grant_id), agent_id, reason)
            if res.get("ok"):
                world.access_changed()
            return res

        async def get_access_matrix() -> dict:
            """Who can read what: the default policy per dataset, the extra grants and the pending requests."""
            return files.access_matrix()
        tools += [list_access_requests, review_access_request, revoke_data_access, get_access_matrix]

    # ------------------------------------------------------------------ Reporting & Insights: dashboards
    if me.dept == "bi" or agent_id in DASHBOARD_MAKERS:
        async def create_dashboard(title: str, description: str, charts_json: str, kpis_json: str = "") -> dict:
            """Publish a dashboard built on the live company data. It appears in the Work files, on screens, and can be downloaded (HTML / CSV).
            description: who it is for and what decisions it supports. kpis_json: optional JSON list of {"label":..., "value":...} headline tiles. """ + CHART_HELP
            try:
                charts, errors = files.run_charts(agent_id, _loads(charts_json, []))
                kpis = _loads(kpis_json, [])
            except ValueError as e:
                return {"error": str(e)}
            if not charts:
                return {"error": "no chart could be built: " + "; ".join(errors)}
            f = files.create("dashboard", title, agent_id, {"description": description[:600], "charts": charts,
                                                            "kpis": [k for k in kpis if isinstance(k, dict)][:6]}, summary=description[:200])
            out = publish(f, "Dashboard live")
            if errors:
                out["chart_errors"] = errors
            return out
        tools.append(create_dashboard)

    # ------------------------------------------------------------------ IT & Apps: internal apps
    if me.dept == "it":
        async def get_app_backlog() -> dict:
            """The app requests waiting for IT (from colleagues, from the company's numbers, and from the CEO), with the business
            signals behind them. Rank them with prioritise_app_requests; build one with create_app(..., request_id=<id>)."""
            ar = company.app_requests
            k = company.store.kpis(7)
            return {"open": await list_app_requests(), "counts": ar.counts(), "apps_live": len(files.list(kind="app")),
                    "last_7_days": k[-1] if k else {}}

        async def prioritise_app_requests(ranking_json: str, summary: str = "") -> dict:
            """Rank the app backlog. ranking_json: JSON list in priority order (most important first) of
            {"id": <request id>, "decision": "build|later|decline", "note": "why, citing the numbers"}. summary: one line for the team."""
            try:
                ranking = _loads(ranking_json, [])
            except ValueError as e:
                return {"error": f"ranking_json {e}"}
            if not isinstance(ranking, list) or not ranking:
                return {"error": "ranking_json must be a non-empty JSON list"}
            res = company.app_requests.prioritise(agent_id, ranking)
            if res["ok"]:
                world.say(agent_id, f"🗂️ App backlog ranked: {summary or str(len(res['updated'])) + ' requests'}"[:140], 4500)
            return res

        tools += [get_app_backlog, prioritise_app_requests]

        async def create_app(title: str, description: str, html: str, data_queries_json: str, request_id: int = 0) -> dict:
            """Build an internal web app (a single self-contained HTML page with inline CSS/JS, no external scripts or network calls).
            data_queries_json: JSON object {"name": "SELECT ..."} of datasets the app needs; their results are injected as
            window.HQ_DATA[name] = {columns:[...], rows:[[...],...]} so the app can render tables, filters and charts (use <canvas> or SVG).
            The app runs sandboxed in the browser and can be downloaded.
            request_id: the app request this delivers (from get_app_backlog), so the team that asked is told it is live."""
            try:
                qs = _loads(data_queries_json, {})
            except ValueError as e:
                return {"error": f"data_queries_json {e}"}
            if not isinstance(qs, dict) or not qs:
                return {"error": "data_queries_json must be a JSON object of name -> SQL"}
            if len(html) < 80 or "<" not in html:
                return {"error": "html must be a complete page or body markup"}
            if "<script src" in html.lower() or "fetch(" in html or "XMLHttpRequest" in html:
                return {"error": "the app must be self-contained: no external scripts and no network calls; use window.HQ_DATA"}
            data, errors = {}, []
            for name, sql in list(qs.items())[:6]:
                ch, err = files.run_charts(agent_id, [{"title": name, "type": "table", "sql": sql}])
                if ch:
                    data[str(name)[:40]] = {"columns": ch[0]["columns"], "rows": ch[0]["rows"]}
                errors += err
            if not data:
                return {"error": "no dataset could be loaded: " + "; ".join(errors)}
            f = files.create("app", title, agent_id, {"description": description[:600], "html": html[:60000], "data": data}, summary=description[:200])
            out = publish(f, "App deployed")
            if errors:
                out["data_errors"] = errors
            if request_id:
                req = company.app_requests.complete(int(request_id), f["id"])
                if req:
                    out["delivered_request"] = req["id"]
                    team = DEPARTMENTS[req["dept"]].name if req["dept"] in DEPARTMENTS else "the CEO"
                    world.log(f"🧩 {me.name} shipped '{title}' for {team}")
                    if req["requester"] in AGENTS:
                        world.remember(req["requester"], "work", f"IT built the app I asked for: '{title}' ({f['id']}). Use it for: {req['use_case'][:200]}", .7)
                    world.remember(agent_id, "work", f"I built '{title}' ({f['id']}) for request {req['id']}: {req['use_case'][:200]}", .6)
            return out
        tools.append(create_app)

    # ------------------------------------------------------------------ People & Culture: hire new AI agents
    if me.dept == "people":
        async def hire_agent(dept: str, name: str, role: str, reason: str) -> dict:
            """Hire a NEW AI agent into a department because of a real requirement (capacity gap, new capability, approved hiring initiative).
            dept: department id; name: the new colleague's full name; role: job title; reason: the requirement it fills (cite data).
            The new agent gets a desk in that department and starts working with the team. Departments have at most """ + str(MAX_PER_DEPT) + " desks."
            if dept not in DEPARTMENTS:
                return {"error": f"unknown department; choose from {sorted(DEPARTMENTS)}"}
            if len(reason.strip()) < 15:
                return {"error": "give the business reason for the hire"}
            try:
                spec = await world.hire(name, role, dept, agent_id, reason)
            except ValueError as e:
                return {"error": str(e)}
            return {"ok": True, "agent_id": spec.id, "name": spec.name, "role": spec.role, "dept": dept,
                    "team_size": len(DEPARTMENTS[dept].agents)}
        tools.append(hire_agent)
    return tools
