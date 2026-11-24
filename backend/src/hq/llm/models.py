"""Choose the model for an agent: real Gemini via ADK when a key is configured, otherwise the deterministic mock."""
from __future__ import annotations

from google.adk.models.base_llm import BaseLlm

from hq.core.config import Settings
from hq.llm.guarded import GuardedGemini
from hq.llm.mock import MockLlm


def make_model(settings: Settings, *, pro: bool = False, owner: str = "") -> str | BaseLlm:
    if settings.use_mock:
        return MockLlm(model="mock-gemini", step_delay=settings.step_delay, owner=owner)
    return GuardedGemini(model=settings.model_pro if pro else settings.model_fast, owner=owner)
