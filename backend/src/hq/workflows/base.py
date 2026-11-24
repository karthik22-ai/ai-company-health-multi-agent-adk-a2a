"""Shared plumbing for LangGraph workflows: run records, the assign() helper, and the node decorator."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable, Literal

from langgraph.errors import GraphInterrupt
from pydantic import BaseModel, Field

from hq.agents.roster import AGENTS, DEPARTMENTS, dept_lead
from hq.core.services import Services
from hq.core.world import Task

RunStatus = Literal["running", "awaiting_approval", "completed", "failed", "cancelled"]


class StepRecord(BaseModel):
    node: str
    label: str
    status: Literal["running", "done", "failed"] = "running"
    started: float = Field(default_factory=time.time)
    finished: float | None = None
    task_ids: list[str] = Field(default_factory=list)


class WorkflowRun(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    title: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: RunStatus = "running"
    steps: list[StepRecord] = Field(default_factory=list)
    approval: dict[str, Any] | None = None       # pending human approval request
    result: dict[str, Any] | None = None
    error: str | None = None
    started: float = Field(default_factory=time.time)
    finished: float | None = None


class Ctx:
    """What workflow nodes get: services plus helpers bound to one run."""

    def __init__(self, svc: Services, run: WorkflowRun):
        self.svc, self.run = svc, run
        self.world, self.runtime = svc.world, svc.runtime

    # ------------------------------------------------------------------ steps
    def step(self, node: str, label: str) -> Callable:
        """Decorator: records the step, logs it to the UI and converts failures into a failed run."""
        def deco(fn: Callable[[dict], Awaitable[dict | None]]) -> Callable:
            async def wrapper(state: dict) -> dict:
                rec = next((s for s in self.run.steps if s.node == node), None)
                if rec is None:
                    rec = StepRecord(node=node, label=label)
                    self.run.steps.append(rec)
                    self.world.log(f"▶ {self.run.title} · {label}")
                try:
                    out = await fn(state)
                except GraphInterrupt:
                    raise
                except Exception:
                    rec.status, rec.finished = "failed", time.time()
                    raise
                rec.status, rec.finished = "done", time.time()
                return out or {}
            wrapper.__name__ = node
            return wrapper
        return deco

    def _rec(self, node: str) -> StepRecord | None:
        return next((s for s in self.run.steps if s.node == node), None)

    # ------------------------------------------------------------------ work
    async def assign(self, node: str, agent: str, title: str, instructions: str, *, mock: dict | None = None,
                     context: dict | None = None) -> Task:
        t = self.world.new_task(agent, title, instructions, source=f"workflow:{self.run.name}/{self.run.id}")
        rec = self._rec(node)
        if rec:
            rec.task_ids.append(t.id)
        await self.runtime.run_task(t, mock=mock, context=context)
        return self.world.tasks[t.id]

    async def pause(self, seconds: float) -> None:
        await asyncio.sleep(seconds * max(self.svc.settings.step_delay, 0.0))

    # ------------------------------------------------------------------ explicit, user-requested movement
    async def gather(self, room: str, agents: list[str], topic: str, seconds: float = 6.0) -> None:
        """Meeting: only used when the run was started with use_meetings=true (i.e. the user asked for it)."""
        w = self.world
        w.meeting(room, agents, topic)
        for a in agents:
            w.set_status(a, "meeting", topic)
        await self.pause(seconds)
        w.end_meeting(room)
        for a in agents:
            w.set_status(a, "idle", "Back at desk")

    async def present_round(self, room: str, agents: list[str], topic: str) -> None:
        """A meeting where each attendee presents their work on the room screen (slides written by the agent itself)."""
        w = self.world
        w.meeting(room, agents, topic)
        for a in agents:
            w.set_status(a, "meeting", topic)
        await self.pause(10)                              # time to walk in (and ride the lift)
        for a in agents:
            slides = await self.runtime.slides(a)
            w.present(a, slides)
            await self.pause(8 * len(slides) + 5)         # presenter walks to the screen, talks, walks back
        w.end_meeting(room)
        for a in agents:
            w.set_status(a, "idle", "Back at desk")

    def free_room(self) -> str:
        busy = set(self.world.meetings)
        return next((r for r in ["mr1", "mr2", "mr3"] if r not in busy), "brd")

    async def resolve_blocked(self, task: Task, state: dict) -> Task:
        """A blocked task is handed to the department lead (a real agent task); then the work is retried with their answer."""
        spec = AGENTS[task.agent]
        lead = dept_lead(spec.dept)
        helper = lead if lead.id != spec.id else next(a for a in DEPARTMENTS[spec.dept].agents if a.id != spec.id)
        reason = task.note or "blocked"
        if state.get("params", {}).get("use_meetings"):
            await self.gather(self.free_room(), [spec.id, helper.id], f"Unblock: {task.title}", 5.0)
        fix = await self.assign(
            f"unblock-{task.id}", helper.id, f"Unblock {spec.name.split()[0]}: {task.title}",
            f"{spec.name} is blocked on '{task.title}': {reason}. Decide how to resolve it and state the resolution in one sentence.",
            mock={"final_note": "Resolution agreed: proceed with the latest available figures and follow up."},
        )
        retry = self.world.new_task(task.agent, f"{task.title} (resumed)",
                                    f"{task.instructions}\nThe blocker was resolved: {fix.result or 'proceed'}",
                                    source=task.source)
        await self.runtime.run_task(retry, mock={"final_note": "Completed after the blocker was resolved"})
        return self.world.tasks[retry.id]

    def mock_blocker_for(self, agent: str) -> str | None:
        sb = self.run.params.get("simulate_blocker") or {}
        return sb.get("reason") if sb.get("agent") == agent else None


def merge_dict(a: dict | None, b: dict | None) -> dict:
    return {**(a or {}), **(b or {})}


def agent_ids_for_meeting(*ids: str) -> list[str]:
    return [i for i in ids if i in AGENTS]
