"""The company clock: advances the simulated business one day at a time and runs the operating rhythm (LangGraph workflows) each day."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, timedelta
from typing import Any

from hq.agents.roster import AGENTS, dept_lead
from hq.company import initiatives as im
from hq.core.services import Services

log = logging.getLogger("hq.core.clock")
PERMANENT = {"automation", "provider_deal", "new_product", "hire"}


class CompanyRunner:
    def __init__(self, svc: Services):
        self.svc = svc
        self.co = svc.company
        self.world = svc.world
        self.seconds_per_day = svc.settings.sim_seconds_per_day
        self.agents = svc.settings.sim_agents
        self.running = False
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.impl: dict[str, str] = {}           # initiative id -> board task id
        self.last_error: str | None = None
        self.days_run = 0
        self.busy = False                        # a day (and its agent workflows) is being processed

    # ------------------------------------------------------------------ control
    def state(self) -> dict[str, Any]:
        return {"running": self.running, "busy": self.busy, "date": self.co.today.isoformat(), "seconds_per_day": self.seconds_per_day,
                "agents": self.agents, "days_run": self.days_run, "last_error": self.last_error}

    def start(self, seconds_per_day: float | None = None, agents: bool | None = None) -> None:
        if seconds_per_day:
            self.seconds_per_day = max(0.0, float(seconds_per_day))
        if agents is not None:
            self.agents = bool(agents)
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._loop(), name="company-clock")
        self._announce()

    async def pause(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._announce()

    async def step(self, days: int = 1, agents: bool | None = None) -> None:
        use_agents = self.agents if agents is None else agents
        for _ in range(max(1, min(int(days), 400))):
            await self.tick(use_agents)

    def _announce(self) -> None:
        self.world.emit({"type": "clock", **self.state()})

    async def _loop(self) -> None:
        while self.running:
            t0 = time.monotonic()
            try:
                await self.tick(self.agents)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # keep the company running; surface the error
                log.exception("day failed")
                self.last_error = f"{type(e).__name__}: {e}"
                self.world.log(f"⚠ Daily run failed: {self.last_error}")
            await asyncio.sleep(max(self.seconds_per_day - (time.monotonic() - t0), 0.0))

    # ------------------------------------------------------------------ one day
    async def tick(self, agents: bool = True) -> None:
        async with self._lock:
            self.busy = True
            self._announce()
            try:
                res = await asyncio.to_thread(self.co.advance)
                self.days_run += 1
                self._publish(res)
                await self._life(self.co.today, agents)
                self._consolidate()
                if self.co.today.weekday() == 0 and self.co.economy is not None:     # rivals respond to the market weekly
                    for ev in self.co.town.competitors.step(self.co.today):
                        self.world.emit({"type": "town_event", "event": ev, "quiet": False})
                        self.world.log(f"🏁 {ev['text']}")
                self._sync_impl()
                if agents:
                    await self._flows(self.co.today)
                self._sync_impl()
            finally:
                self.busy = False
                self._announce()

    def _publish(self, res: Any) -> None:
        w = self.world
        payload = self.co.dashboard_payload()
        payload["notes_today"] = res.scheduled
        w.biz_day(payload)
        for line in res.scheduled:
            w.log(f"📅 {res.date}: {line}")
        for e in res.events_started:
            w.log(f"🌏 Market event: {e['name']} – {e['desc']}")
        for ini in self.co.sim.initiatives.values():
            if ini["status"] in ("running", "completed") and ini.get("_ui") != ini["status"]:
                ini["_ui"] = ini["status"]
                w.biz_initiative(ini)

    # ------------------------------------------------------------------ life in the town (every day, with or without the agents)
    async def _life(self, d: date, agents: bool) -> None:
        w, town = self.world, self.co.town
        for item in town.life.advance_day(d):
            e = item["event"]
            w.emit({"type": "town_life", **item})
            r = item.get("resident") or {}
            if e["kind"] in ("death",):
                for rel in town.relations(r["id"]):
                    if not rel.get("employee"):
                        w.remember(rel["id"], "life", f"{r['name']} ({rel['relation'].replace(' (passed away)', '')}) passed away.", 1.0)
                    else:
                        w.remember(rel["id"], "life", f"My {rel['relation']} {r['name']} from Wattle Grove passed away.", .8)
            else:
                w.remember(r.get("id", ""), "life", e["text"], .8 if e["kind"] in ("birth", "move_in", "partner", "new_job", "retired") else .4)
                if item.get("other"):
                    w.remember(item["other"], "life", e["text"], .7)
            if e["kind"] in ("birth", "death", "move_in", "partner", "new_job", "retired"):
                w.log(f"🏘 {e['text']}")
        if d.day == 1:
            mayor = town.life.mayor()
            if agents and mayor:
                await self.svc.runtime.resident_task(mayor["id"], "[RESIDENT] You chair the Wattle Grove town council this month. Look at get_town_needs and decide "
                                                     "whether the town should build ONE facility now with build_facility(kind, reason). Think about who lives here.", "council")
            else:
                f = town.life.rule_council(d)
                if f:
                    w.emit({"type": "town_life", "event": {"resident": f["by_res"], "kind": "facility", "text": f"The council approved {f['name']}"}, "facility": f})

    def _consolidate(self) -> None:
        """Nightly memory digests for every employee and resident."""
        town = self.co.town
        for a in list(self.world.agents) + [r["id"] for r in town.residents()]:
            self.world.consolidate(a)
        from hq.quality import traces
        traces.prune(self.co.store)

    # ------------------------------------------------------------------ agents' operating rhythm
    async def _flows(self, d: date) -> None:
        wf = self.svc.workflows
        plan: list[tuple[str, dict[str, Any]]] = [("daily_ops", {})]
        if d.weekday() == 0:
            plan.append(("weekly_strategy", {"week": d.isocalendar()[1]}))
            if self.co.economy is not None:                     # plan → act → reflect: last week's goals reviewed, this week's set
                plan.append(("weekly_goals", {}))
        if d.day == 1:
            plan.append(("monthly_review", {}))
        if d.day == 15:
            plan.append(("team_health", {}))
        if d.weekday() == 4:                                   # Fridays: Reporting & Insights publishes
            plan.append(("reporting_cycle", {"week": d.isocalendar()[1]}))
        if d.weekday() == 1:                                   # Tuesdays: IT works its app backlog (teams' requests + growth signals)
            plan.append(("it_build", {"n": d.isocalendar()[1]}))
        from hq.workflows.teams import pending_hires
        if pending_hires(self.co):                             # an approved hire becomes a real AI agent
            plan.append(("hiring", {}))
        if d.weekday() == 2:                                   # Wednesdays: Marketing works on the town
            plan.append(("town_marketing", {}))
        if d.weekday() == 3:                                   # Thursdays: leadership meeting in the Boardroom (decks + minutes)
            s = self.co.sales(0) if hasattr(self.co, "sales") and self.co.economy is not None else None
            facts = f" We have {s['members_now']} members; {s['sold']['7d']} sold and {s['lost']['7d']} lost in the last 7 days." if s else ""
            plan.append(("meeting", {"room": "brd", "attendees": ["exec.priya", "mkt.grace", "sales.leo", "bi.olivia"],
                                     "agenda": "Weekly leadership: how do we win and keep more members?" + facts
                                               + " Each of you: what worked this week, what didn't, and one thing to try next week."}))
        yr = d.year if d.month < 4 else d.year + 1
        done = self.co.store.get_kv("premium_round_done", None)
        if done != yr and ((d.month == 2 and d.day >= 15) or d.month == 3) and not self.co.sim.s["pending_prices"] and d.month * 100 + d.day <= 325:
            plan.append(("premium_round", {}))
            self.co.store.set_kv("premium_round_done", yr)
        background = self.running                 # running on its own: workflows run alongside the days instead of blocking them
        for name, params in plan:
            if background and any(r.name == name and r.status in ("running", "awaiting_approval") for r in wf.runs.values()):
                continue                              # the previous one is still working: don't pile up
            run = await wf.start(name, {**params, "auto_approve": True})
            if background:
                continue
            try:
                await wf.wait(run.id, 1800)
            except asyncio.TimeoutError:
                self.world.log(f"⚠ {name} took too long and was left running")
            if run.status == "failed":
                self.world.log(f"⚠ {name} failed: {run.error}")

    # ------------------------------------------------------------------ board tasks for approved initiatives
    def _sync_impl(self) -> None:
        w = self.world
        today = self.co.today
        for ini in self.co.sim.initiatives.values():
            if ini["status"] not in ("approved", "running", "completed") or not ini.get("start_date"):
                continue
            owner = ini["proposer"] if ini["proposer"] in AGENTS else dept_lead(ini["dept"] if ini["dept"] in {a.dept for a in AGENTS.values()} else "exec").id
            task = w.tasks.get(self.impl.get(ini["id"], ""))
            if task is None:
                task = w.new_task(owner, f"Deliver {ini['id']}: {ini['title']}"[:110], ini.get("rationale", ""), source=f"initiative:{ini['id']}")
                self.impl[ini["id"]] = task.id
            start = date.fromisoformat(ini["start_date"])
            lead = im.LEAD_DAYS.get(ini["kind"], 7)
            if ini["status"] == "completed":
                if task.status != "done":
                    w.update_task(task, status="done", progress=100, note="Delivered; effects being measured")
                continue
            if today < start:
                span = max(lead, 1)
                prog = int(min(100, max(0, 100 - (start - today).days / span * 100)) * 0.3)
                w.update_task(task, status="doing" if prog > 0 else "todo", progress=prog, note=f"Starts {start.isoformat()}")
            else:
                end = date.fromisoformat(ini["end_date"]) if ini.get("end_date") else start + timedelta(days=90)
                total = max((end - start).days, 1)
                prog = int(min(100, 30 + (today - start).days / total * 70))
                w.update_task(task, status="doing", progress=prog, note=f"Running since {start.isoformat()}")
