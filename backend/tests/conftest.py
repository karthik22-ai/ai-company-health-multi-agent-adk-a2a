from contextlib import AsyncExitStack

import pytest
from fastapi import FastAPI

from hq.a2a.host import mount_a2a_agents
from hq.core.config import Settings
from hq.core.services import build_services


@pytest.fixture
def settings(tmp_path):
    return Settings(mock_llm=True, step_delay=0.0, persist=False, data_dir=tmp_path, google_api_key=None, sim_history_days=120, economy="synthetic")


@pytest.fixture
async def svc(settings):
    """Services + an app that serves every agent over A2A (in-process ASGI transport)."""
    s = build_services(settings)
    app = FastAPI()
    async with AsyncExitStack() as stack:
        s.cards = await mount_a2a_agents(app, s.runtime, settings, stack)
        s.peers.bind_asgi(app)
        yield s
        await s.peers.aclose()


@pytest.fixture
async def town_svc(tmp_path):
    """The live configuration: the company's numbers come only from the town agents."""
    st = Settings(mock_llm=True, step_delay=0.0, persist=False, data_dir=tmp_path / "town", google_api_key=None, economy="town")
    s = build_services(st)
    app = FastAPI()
    async with AsyncExitStack() as stack:
        s.cards = await mount_a2a_agents(app, s.runtime, st, stack)
        s.peers.bind_asgi(app)
        yield s
        await s.peers.aclose()
