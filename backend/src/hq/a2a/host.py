"""Expose every ADK agent as an A2A server, mounted at /a2a/<agent_id>/ on the main FastAPI app."""
from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from fastapi import FastAPI
from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from hq.agents.runtime import AgentRuntime
from hq.core.config import Settings

log = logging.getLogger("hq.a2a.host")


async def mount_a2a_agents(app: FastAPI, runtime: AgentRuntime, settings: Settings, stack: AsyncExitStack) -> dict[str, Any]:
    """Build one A2A application per agent and mount it. Returns {agent_id: agent_card}.

    `to_a2a` attaches its routes inside the sub-app's lifespan, and Starlette does not run lifespans of mounted
    apps – so we enter each sub-app lifespan ourselves through the exit stack owned by the main app.
    """
    cards: dict[str, Any] = {}
    for agent_id in list(runtime.agents):
        cards[agent_id] = await mount_one(app, runtime, settings, stack, agent_id)
    log.info("mounted %d A2A agents", len(cards))
    return cards


async def mount_one(app: FastAPI, runtime: AgentRuntime, settings: Settings, stack: AsyncExitStack, agent_id: str) -> Any:
    """Mount one agent's A2A server (also used at runtime when People & Culture hires a new agent)."""
    agent = runtime.agents[agent_id]
    card = await AgentCardBuilder(agent=agent, rpc_url=f"{settings.base_url}/a2a/{agent_id}/").build()
    # the builder strips the trailing slash, but the sub-app's JSON-RPC route lives at "/" under the mount;
    # without the slash Starlette answers POSTs with a 307 that A2A clients do not follow.
    for iface in card.supported_interfaces:
        if not iface.url.endswith("/"):
            iface.url += "/"
    sub = to_a2a(agent, agent_card=card, runner=runtime.runners[agent_id])
    await stack.enter_async_context(sub.router.lifespan_context(sub))
    app.mount(f"/a2a/{agent_id}", sub)
    return card
