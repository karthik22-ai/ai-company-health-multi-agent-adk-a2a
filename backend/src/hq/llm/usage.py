"""Token metering: every model call reports its token usage against the agent (or resident) that made it."""
from __future__ import annotations

from typing import Any, Callable

SINK: Callable[[str, int, int], None] | None = None    # set by services: (owner, prompt_tokens, output_tokens) -> stored per day


def record(owner: str, prompt_tokens: int, output_tokens: int) -> None:
    if SINK and owner:
        try:
            SINK(owner, int(prompt_tokens or 0), int(output_tokens or 0))
        except Exception:  # noqa: BLE001 - metering must never break a model call
            pass


def from_response(owner: str, resp: Any) -> None:
    u = getattr(resp, "usage_metadata", None)
    if u is None:
        return
    out = (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
    record(owner, getattr(u, "prompt_token_count", 0) or 0, out)
