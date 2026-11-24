"""Runtime configuration (environment variables / .env)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]       # backend/  (this file is backend/src/hq/core/config.py)
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HQ_", env_file=str(BACKEND_DIR / ".env"), extra="ignore", populate_by_name=True
    )

    # --- LLM ---
    google_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GOOGLE_API_KEY", "HQ_GOOGLE_API_KEY"))
    # Vertex AI on your own Google Cloud project (Application Default Credentials – no key stored anywhere)
    use_vertex: bool = False
    gcp_project: str | None = Field(default=None, validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT", "HQ_GCP_PROJECT"))
    gcp_location: str = Field(default="global", validation_alias=AliasChoices("GOOGLE_CLOUD_LOCATION", "HQ_GCP_LOCATION"))
    model_fast: str = "gemini-3.5-flash"        # everyday agents
    model_pro: str = "gemini-3.1-pro-preview"   # department heads / CFO
    pro_agents: list[str] = ["exec.priya", "exec.daniel"]   # only the final decision makers use the slower Pro model
    mock_llm: bool | None = None                # None -> mock when there is no API key

    # --- server ---
    host: str = "127.0.0.1"
    port: int = 8787
    auth_token: str | None = None
    ui_dir: Path = PROJECT_DIR / "frontend"          # index.html, css/, js/ (js/manifest.json sets the order of the modules)
    data_dir: Path = BACKEND_DIR / "data"

    # --- behaviour ---
    step_delay: float = 1.0          # pacing of the mock LLM
    auto_meetings: bool = False      # agents never walk to meetings on their own unless enabled
    a2a_transport: Literal["asgi", "http"] = "asgi"
    public_url: str | None = None    # defaults to http://<host>:<port>; what agent cards advertise to external A2A clients
    persist: bool = True

    # --- the synthetic company ---
    sim_seed: int = 7
    sim_start: str = "2026-03-02"        # the first simulated 'today' (a Monday); a year of history is generated before it
    sim_seconds_per_day: float = 45.0    # real seconds per simulated day when the clock runs
    sim_autostart: bool = False          # start the daily clock when the server starts
    sim_history_days: int = 365          # days of history generated on first run
    economy: str = "town"              # town = the company's numbers come only from the town agents; synthetic = the old generator
    town_tick_seconds: float = 12.0      # how often the town loop runs (health care, decisions, plans)
    town_decisions_per_minute: float = 2.0
    town_real_web: bool = True        # residents' search_web uses Google Search through Gemini (when not in mock mode)
    town_shoppers_per_day: int = 6     # how many households may review their cover each simulated day
    sim_agents: bool = True              # run the agent workflows each day (needs LLM calls); False = data only

    @property
    def base_url(self) -> str:
        return (self.public_url or f"http://{self.host}:{self.port}").rstrip("/")

    @property
    def use_mock(self) -> bool:
        if self.mock_llm is not None:
            return self.mock_llm
        return not (self.use_vertex or self.google_api_key)

    @property
    def llm_label(self) -> str:
        if self.use_mock:
            return "mock (set HQ_USE_VERTEX=true or GOOGLE_API_KEY for Gemini)"
        if self.use_vertex:
            return f"Vertex AI · {self.gcp_project} · {self.gcp_location} · {self.model_fast}"
        return f"Gemini API · {self.model_fast}"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.use_vertex:
        if not s.gcp_project:
            raise RuntimeError("HQ_USE_VERTEX=true needs GOOGLE_CLOUD_PROJECT (your Google Cloud project id)")
        # google-genai reads these; it refuses to start if an API key is set together with Vertex, so drop the key
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        os.environ["GOOGLE_CLOUD_PROJECT"] = s.gcp_project
        os.environ["GOOGLE_CLOUD_LOCATION"] = s.gcp_location
        os.environ.pop("GOOGLE_API_KEY", None)
    elif s.google_api_key and not s.use_mock:
        os.environ.setdefault("GOOGLE_API_KEY", s.google_api_key)
    return s
