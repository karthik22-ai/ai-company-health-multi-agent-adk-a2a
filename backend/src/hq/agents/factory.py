"""The agent factory: the ONE place where every AI agent in the simulation is created.

Two kinds of agents:

  employee   one per person on the roster (agents/roster.py) plus anyone People & Culture hires later.
             Built twice: a *work* agent (runs tasks for workflows, talks to colleagues over A2A) and a *chat* agent (talks to you,
             may walk to a meeting room when asked). Same persona, model and memory; the chat agent has two extra tools.
  resident   one per Wattle Grove resident (town/). Built fresh for each run so it always sees its current life
             (age, home, job, fund, relations, memories).

Every agent is assembled from the same parts:

  persona    who they are                          agents/personas.py
  context    the real market situation (employees) built here (market_block)
  memory     their own long-term memory             core/world.py (remember / memories)
  model      Gemini via Vertex AI, or the offline mock, metered per agent    llm/models.py
  toolsets   what they can do                       agents/tools/*.py, chosen per kind below

To add a new kind of agent or give a role new abilities, change this file (and the toolset modules), nothing else.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from hq.agents.personas import persona, resident_persona
from hq.agents.roster import AGENTS, DEPARTMENTS, AgentSpec, adk_name
from hq.agents.tools.business import make_biz_tools
from hq.agents.tools.core import make_tools as make_core_tools
from hq.agents.tools.resident import make_resident_tools
from hq.agents.tools.work import make_work_tools
from hq.llm.models import make_model

log = logging.getLogger("hq.agents.factory")

APP, CHAT_APP, TOWN_APP = "ai-company-hq", "ai-company-hq-chat", "ai-company-town"

# toolsets every employee gets, in order (each maker decides internally what a department/role may use)
EMPLOYEE_TOOLSETS: list[tuple[str, Callable[..., list]]] = [
    ("core", lambda spec, f, chat: make_core_tools(spec.id, f.world, f.peers, f.settings, chat=chat)),   # status, progress, A2A, memory
    ("business", lambda spec, f, chat: make_biz_tools(spec.id, f.world)),                                # KPIs, SQL, initiatives, decisions
    ("work", lambda spec, f, chat: make_work_tools(spec.id, f.world)),                                   # files, dashboards, apps, access, hiring, town
]


def _config(temperature: float) -> types.GenerateContentConfig:
    # an occasional Gemini request stalls with no response: fail fast and retry instead of hanging the whole day
    return types.GenerateContentConfig(temperature=temperature,
                                       http_options=types.HttpOptions(timeout=70_000, retry_options=types.HttpRetryOptions(attempts=4, initial_delay=1.0, max_delay=8.0)))


def _current_text(ctx: Any) -> str:
    """What the agent is being asked right now (used to recall the most relevant memories)."""
    try:
        parts = ctx.user_content.parts if ctx.user_content else []
        return " ".join(p.text or "" for p in parts if getattr(p, "text", None))[-600:]
    except AttributeError:
        return ""


class AgentFactory:
    def __init__(self, settings: Any, world: Any, peers: Any, runtime: Any, sessions: Any):
        self.settings, self.world, self.peers, self.runtime, self.sessions = settings, world, peers, runtime, sessions

    # ------------------------------------------------------------------ employees
    def employee_tools(self, spec: AgentSpec, chat: bool = False) -> list[Callable]:
        tools: list[Callable] = []
        for _name, maker in EMPLOYEE_TOOLSETS:
            tools += maker(spec, self, chat)
        return tools

    def employee_instruction(self, spec: AgentSpec) -> Callable[[Any], str]:
        """Built per call, so the agent always sees the latest market situation and its own latest memories."""
        def build(ctx: Any) -> str:
            return persona(spec) + self.market_block() + self.world.memory_block(spec.id, query=_current_text(ctx))
        return build

    def employee(self, spec: AgentSpec) -> tuple[LlmAgent, LlmAgent, Runner, Runner]:
        """The work agent and the chat agent for one employee, with their runners."""
        common = dict(model=make_model(self.settings, pro=spec.id in self.settings.pro_agents, owner=spec.id),
                      description=f"{spec.name} – {spec.role} ({DEPARTMENTS[spec.dept].name})",
                      instruction=self.employee_instruction(spec), generate_content_config=_config(0.3))
        work = LlmAgent(name=adk_name(spec.id), tools=self.employee_tools(spec), **common)
        chat = LlmAgent(name=adk_name(spec.id) + "_chat", tools=self.employee_tools(spec, chat=True), **common)
        return (work, chat,
                Runner(app_name=APP, agent=work, session_service=self.sessions, auto_create_session=True),
                Runner(app_name=CHAT_APP, agent=chat, session_service=self.sessions, auto_create_session=True))

    def all_employees(self) -> list[AgentSpec]:
        return list(AGENTS.values())

    # ------------------------------------------------------------------ residents
    def resident(self, rid: str) -> Runner:
        """A town resident's agent, built fresh so it reflects their life right now."""
        town = self.world.company.town
        r = town.resident(rid)
        agent = LlmAgent(name=f"resident_{rid}", model=make_model(self.settings, owner=rid), description=f"{r['name']}, town resident",
                         instruction=resident_persona(r, town.relations(rid)) + self.world.memory_block(rid, 10),
                         tools=make_resident_tools(rid, self.world, self.runtime, self.settings), generate_content_config=_config(0.7))
        return Runner(app_name=TOWN_APP, agent=agent, session_service=self.sessions, auto_create_session=True)

    # ------------------------------------------------------------------ shared context
    def market_block(self) -> str:
        """Where the company really stands: its numbers come only from the Wattle Grove residents' decisions."""
        co = self.world.company
        if co is None or getattr(co, "economy", None) is None:
            return ""
        from hq.town.town import INSURERS
        res = co.town.residents()
        share: dict[str, int] = {}
        for r in res:
            k = (r.get("cover") or {}).get("insurer") or "none"
            share[k] = share.get(k, 0) + 1
        top = ", ".join(f"{INSURERS.get(k, {}).get('name', k)} {v}" for k, v in sorted(share.items(), key=lambda x: -x[1]))
        return (f"\nTHE REAL SITUATION (overrides the generic business description above): AI Company Health competes for members in Wattle Grove, a town of "
                f"{len(res)} residents (AI agents with their own lives). Health insurance membership is mandatory there; people choose among real Australian funds "
                f"and us. People covered now: {top}. Every company number (members, sales, claims, revenue) comes ONLY from what these residents do. We own the "
                "AI Company Health Private Hospital and Clinic (no gap for members). The company's goal is to win and keep members: try different tactics "
                "(campaigns, new-member offers, perks, workplace group deals, better service, preventive health, retention) and learn from what works. "
                "Use get_membership_funnel and get_town_insights." + self._rivals())

    def _rivals(self) -> str:
        from hq.town.town import INSURERS
        act = self.world.company.town.competitors.active()
        if not act:
            return ""
        return " Competitor moves running now: " + "; ".join(f"{INSURERS[k]['name']}: {v['text']} until {v['until']}" for k, v in act.items()) + "."


    # ------------------------------------------------------------------ catalogue (what exists and what each agent can do)
    def describe(self) -> dict[str, Any]:
        rt = self.runtime
        emp = [{"id": s.id, "name": s.name, "role": s.role, "dept": s.dept, "lead": s.lead,
                "tools": [t.__name__ for t in (rt.agents[s.id].tools if s.id in rt.agents else [])]} for s in self.all_employees()]
        town = self.world.company.town if self.world.company is not None else None
        return {"kinds": {"employee": {"count": len(emp), "toolsets": [n for n, _ in EMPLOYEE_TOOLSETS], "apps": [APP, CHAT_APP]},
                          "resident": {"count": len(town.residents()) if town else 0, "app": TOWN_APP,
                                       "tools": [t.__name__ for t in make_resident_tools("r001", self.world, rt, self.settings)] if town and town.resident("r001") else []}},
                "employees": emp}
