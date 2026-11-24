"""Service container: builds and wires world, bus, A2A peers and the ADK runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hq.a2a.peers import A2APeers
from hq.agents.runtime import AgentRuntime
from hq.company.company import Company
from hq.core.bus import EventBus, EventLog
from hq.core.config import Settings, get_settings
from hq.core.world import World


@dataclass
class Services:
    settings: Settings
    bus: EventBus
    world: World
    peers: A2APeers
    runtime: AgentRuntime
    company: Company | None = None
    cards: dict[str, Any] = field(default_factory=dict)
    workflows: Any = None           # WorkflowManager, attached by the app
    runner: Any = None              # CompanyRunner (daily clock), attached by the app
    evals: Any = None               # quality/evals.py, created on first use
    app: Any = None                 # the FastAPI app (to mount A2A endpoints for new hires)
    a2a_stack: Any = None           # AsyncExitStack owning the A2A sub-app lifespans
    rooms: Any = None               # RoomTalk: messages, @mentions and raise-hand turns per room
    town_loop: Any = None           # TownLoop: residents live continuously


def build_services(settings: Settings | None = None, remote_agents: dict[str, str] | None = None) -> Services:
    settings = settings or get_settings()
    log_path = (settings.data_dir / "events.jsonl") if settings.persist else None
    bus = EventBus(EventLog(log_path))
    from datetime import date as _date
    company = Company(settings.data_dir / "company.db", seed=settings.sim_seed, start=_date.fromisoformat(settings.sim_start), economy=settings.economy)
    from hq.agents.roster import add_agent
    for h in company.files.hires():                 # AI agents hired by People & Culture in earlier sessions
        try:
            add_agent(h["name"], h["role"], h["dept"], aid=h["id"])
        except ValueError:
            pass
    world = World(bus)
    world.company = company
    company.guard.world = world
    peers = A2APeers(settings, world, remote_agents)
    runtime = AgentRuntime(settings, world, peers)
    peers.runtime = runtime
    svc = Services(settings, bus, world, peers, runtime, company)
    from hq.workflows.manager import WorkflowManager  # imported late: workflows import Services
    svc.workflows = WorkflowManager(svc)
    from hq.core.rooms import RoomTalk
    svc.rooms = RoomTalk(svc)

    async def on_hire(spec) -> None:                  # a hire becomes a real ADK agent with its own A2A endpoint
        runtime.add_employee(spec)
        if svc.app is not None and svc.a2a_stack is not None:
            from hq.a2a.host import mount_one
            svc.cards[spec.id] = await mount_one(svc.app, runtime, settings, svc.a2a_stack, spec.id)
    world.on_hire.append(on_hire)

    import datetime as _dt

    from hq.llm import usage as _usage

    def sink(owner: str, pin: int, pout: int) -> None:          # tokens per person per (real) day
        day = _dt.date.today().isoformat()
        company.store.db.execute("INSERT INTO token_usage VALUES (?,?,?,?,1) ON CONFLICT(owner, day) DO UPDATE SET prompt=prompt+excluded.prompt, "
                                 "output=output+excluded.output, calls=calls+1", (owner, day, pin, pout))
        company.store.commit()
    _usage.SINK = sink

    def on_access() -> None:                          # new access requests: the Data team reviews them
        if company.files.access_requests("pending") and not any(r.name == "access_review" and r.status == "running" for r in svc.workflows.runs.values()):
            import asyncio
            try:
                asyncio.get_running_loop().create_task(svc.workflows.start("access_review", {}))
            except RuntimeError:
                pass
    world.on_access.append(on_access)
    return svc
