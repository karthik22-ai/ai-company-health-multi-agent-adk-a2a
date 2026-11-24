"""Runs LangGraph workflows, tracks runs, handles the human approval (interrupt/resume) and reports to the UI."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from langgraph.types import Command

from hq.core.services import Services
from hq.workflows.base import Ctx, WorkflowRun

log = logging.getLogger("hq.workflows")
from hq.workflows.operations import DAILY_OPS, MONTHLY_REVIEW, PREMIUM_ROUND, TEAM_HEALTH, WEEKLY_STRATEGY
from hq.workflows.quality import WEEKLY_GOALS
from hq.workflows.teams import ACCESS_REVIEW, HIRING, IT_BUILD, MEETING, REPORTING, TOWN_DAY, TOWN_MARKETING, WORK_REQUEST

CATALOG: dict[str, dict] = {w["name"]: w for w in (DAILY_OPS, WEEKLY_STRATEGY, MONTHLY_REVIEW, PREMIUM_ROUND, TEAM_HEALTH,
                                                     MEETING, REPORTING, IT_BUILD, ACCESS_REVIEW, HIRING, WORK_REQUEST, TOWN_DAY, TOWN_MARKETING, WEEKLY_GOALS)}


class WorkflowManager:
    def __init__(self, svc: Services):
        self.svc = svc
        self.runs: dict[str, WorkflowRun] = {}
        self._decisions: dict[str, asyncio.Future] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------ catalog / queries
    def catalog(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in w.items() if k != "build"} for w in CATALOG.values()]

    def list(self) -> list[WorkflowRun]:
        return sorted(self.runs.values(), key=lambda r: r.started, reverse=True)

    # ------------------------------------------------------------------ lifecycle
    async def start(self, name: str, params: dict[str, Any] | None = None) -> WorkflowRun:
        if name not in CATALOG:
            raise KeyError(f"unknown workflow '{name}'. Available: {sorted(CATALOG)}")
        spec = CATALOG[name]
        run = WorkflowRun(name=name, title=spec["title"], params=params or {})
        self.runs[run.id] = run
        graph = spec["build"](Ctx(self.svc, run))
        self.svc.world.log(f"◆ {run.title} started (run {run.id})")
        self._tasks[run.id] = asyncio.create_task(self._drive(run, graph), name=f"workflow-{run.id}")
        return run

    async def cancel(self, run_id: str) -> bool:
        t = self._tasks.get(run_id)
        run = self.runs.get(run_id)
        if not t or not run or run.status not in ("running", "awaiting_approval"):
            return False
        t.cancel()
        run.status, run.finished = "cancelled", time.time()
        self.svc.world.log(f"■ {run.title} cancelled")
        return True

    def approve(self, run_id: str, approved: bool = True, note: str = "") -> bool:
        fut = self._decisions.get(run_id)
        if not fut or fut.done():
            return False
        fut.set_result({"approved": approved, "note": note})
        return True

    async def wait(self, run_id: str, timeout: float | None = None) -> WorkflowRun:
        await asyncio.wait_for(asyncio.shield(self._tasks[run_id]), timeout)
        return self.runs[run_id]

    # ------------------------------------------------------------------ driver
    async def _drive(self, run: WorkflowRun, graph: Any) -> None:
        w = self.svc.world
        cfg = {"configurable": {"thread_id": run.id}}
        started_at = time.time()
        try:
            out = await graph.ainvoke({"params": run.params, "outputs": {}}, cfg)
            while True:
                snap = await graph.aget_state(cfg)
                if not snap.next:                                    # finished
                    break
                payload = next((i.value for t in snap.tasks for i in t.interrupts), {})
                run.status, run.approval = "awaiting_approval", payload
                fut = asyncio.get_running_loop().create_future()
                self._decisions[run.id] = fut
                w.emit({"type": "approval_request", "run": run.id, "title": payload.get("title", run.title),
                        "summary": payload.get("summary", "")})
                w.log(f"⏸ {run.title} is waiting for approval")
                if run.params.get("auto_approve"):
                    await asyncio.sleep(max(self.svc.settings.step_delay, 0) * 2)
                    self.approve(run.id, True, "auto-approved")
                decision = await fut
                run.status, run.approval = "running", None
                w.emit({"type": "approval_resolved", "run": run.id, "approved": decision["approved"]})
                w.log(f"{'✔ Approved' if decision['approved'] else '✖ Rejected'}: {payload.get('title', run.title)}")
                out = await graph.ainvoke(Command(resume=decision), cfg)
            await self._drain_handoffs(started_at)
            run.result = {"outputs": out.get("outputs", {}), "blockers": out.get("blockers", []),
                          "findings": out.get("findings", []), "approved": out.get("approved")}
            run.status = "completed"
            w.log(f"✔ {run.title} complete")
            await asyncio.sleep(max(self.svc.settings.step_delay, 0) * 5)
            self._relax()
        except asyncio.CancelledError:
            run.status = "cancelled"
            raise
        except Exception as e:  # a failed run must be visible, not silent
            log.exception("workflow %s failed", run.id)
            run.status, run.error = "failed", f"{type(e).__name__}: {e}"
            w.log(f"✖ {run.title} failed: {run.error}")
        finally:
            run.finished = time.time()
            self._decisions.pop(run.id, None)

    async def _drain_handoffs(self, since: float, timeout: float = 120.0) -> None:
        """Hand-offs run in the background over A2A; wait for the ones created during this run."""
        w = self.svc.world
        end = time.time() + timeout
        while time.time() < end:
            open_ = [t for t in w.tasks.values() if t.source.startswith("a2a:") and t.created >= since and t.status in ("todo", "doing")]
            if not open_:
                return
            await asyncio.sleep(0.2)

    def _relax(self) -> None:
        """After a run, agents that were celebrating ('done') go back to idle."""
        w = self.svc.world
        for a in w.agents.values():
            if a.state == "done":
                w.set_status(a.id, "idle", "Idle")
