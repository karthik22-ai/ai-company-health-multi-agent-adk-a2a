"""Gemini wrapper that keeps the simulation inside the Vertex AI quota and keeps the owner's chats fast.

  * a global concurrency cap with priority: calls made while the owner is waiting (chat, talk) go before background work
    (workflows, town residents), which otherwise fill the queue all day
  * background calls are paced (BACKGROUND_RPM) and pause for a while after Vertex answers 429 RESOURCE_EXHAUSTED
  * a hard per-call deadline: under parallel load Vertex occasionally leaves a request hanging and the HTTP timeout does not fire,
    so every call runs as its own task; if it misses the deadline it is abandoned (not awaited) and retried
"""
from __future__ import annotations

import asyncio
import contextvars
import heapq
import itertools
import logging
import os
import time
from contextlib import contextmanager
from typing import AsyncGenerator, Iterator

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

log = logging.getLogger("hq.llm")
MAX_PARALLEL = int(os.environ.get("HQ_LLM_MAX_PARALLEL", "4"))
BACKGROUND_RPM = float(os.environ.get("HQ_LLM_BACKGROUND_RPM", "30"))   # model calls per minute for work nobody is waiting on
COOLDOWN_429 = 20.0
CALL_TIMEOUT = 60.0
ATTEMPTS = 3

FOREGROUND: contextvars.ContextVar[bool] = contextvars.ContextVar("hq_llm_foreground", default=False)


@contextmanager
def foreground() -> Iterator[None]:
    """Mark model calls in this block (and tasks it starts) as the owner waiting for an answer."""
    tok = FOREGROUND.set(True)
    try:
        yield
    finally:
        FOREGROUND.reset(tok)


class _Gate:
    """A semaphore whose waiters are served by priority (0 = foreground first), then arrival order."""

    def __init__(self, n: int):
        self.free, self.q, self.seq = n, [], itertools.count()

    async def acquire(self, prio: int) -> None:
        if self.free > 0 and not self.q:
            self.free -= 1
            return
        fut = asyncio.get_running_loop().create_future()
        heapq.heappush(self.q, (prio, next(self.seq), fut))
        try:
            await fut
        except asyncio.CancelledError:
            if fut.done() and not fut.cancelled():
                self.release()                    # we were handed a slot just as we were cancelled
            else:
                self.q = [x for x in self.q if x[2] is not fut]
                heapq.heapify(self.q)
            raise

    def release(self) -> None:
        while self.q:
            _, _, fut = heapq.heappop(self.q)
            if not fut.done():
                fut.set_result(None)              # hand the slot straight over
                return
        self.free += 1


_gate: _Gate | None = None
_pace = {"next": 0.0, "until": 0.0}
_pace_lock: asyncio.Lock | None = None


def _get_gate() -> _Gate:
    global _gate
    if _gate is None:
        _gate = _Gate(MAX_PARALLEL)
    return _gate


async def _wait_background_turn() -> None:
    """Space background calls BACKGROUND_RPM apart and hold them during a 429 cool-down."""
    global _pace_lock
    if _pace_lock is None:
        _pace_lock = asyncio.Lock()
    async with _pace_lock:
        now = time.monotonic()
        start = max(now, _pace["next"], _pace["until"])
        _pace["next"] = start + 60.0 / max(1.0, BACKGROUND_RPM)
    if start > now:
        await asyncio.sleep(start - now)


QUOTA_HITS: list[float] = []          # monotonic times of 429s (for the ops panel)


def _is_quota(e: BaseException) -> bool:
    s = str(e)
    return "429" in s or "RESOURCE_EXHAUSTED" in s


def stats() -> dict:
    g = _get_gate()
    now = time.monotonic()
    return {"max_parallel": MAX_PARALLEL, "free": g.free, "waiting": len(g.q), "background_rpm": BACKGROUND_RPM,
            "quota_errors_10min": sum(1 for t in QUOTA_HITS if now - t < 600), "quota_errors_60min": sum(1 for t in QUOTA_HITS if now - t < 3600),
            "cooldown_s": round(max(0.0, _pace["until"] - time.monotonic()), 1)}


class GuardedGemini(Gemini):
    owner: str = ""            # the agent / resident this model instance speaks for (token metering)

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        parent = super()
        fg = FOREGROUND.get()

        async def collect() -> list[LlmResponse]:
            return [r async for r in parent.generate_content_async(llm_request, stream=False)]

        last: BaseException | None = None
        gate = _get_gate()
        backoff = 0.0
        for attempt in range(1, ATTEMPTS + 1):
            if backoff:
                await asyncio.sleep(backoff)             # back off without holding a slot
            if not fg:
                await _wait_background_turn()
            await gate.acquire(0 if fg else 1)
            try:
                task = asyncio.ensure_future(collect())
                done, _ = await asyncio.wait({task}, timeout=CALL_TIMEOUT)
                if not done:
                    task.cancel()                       # abandon without awaiting: a stalled socket may never unwind
                    task.add_done_callback(lambda t: t.cancelled() or t.exception())
                    log.warning("%s call stalled >%ss (attempt %d/%d)", self.model, CALL_TIMEOUT, attempt, ATTEMPTS)
                    last = TimeoutError(f"model call stalled > {CALL_TIMEOUT}s")
                    continue
                try:
                    responses = task.result()
                except Exception as e:                  # noqa: BLE001 - retry transient API errors
                    last = e
                    if _is_quota(e):
                        _pace["until"] = max(_pace["until"], time.monotonic() + COOLDOWN_429)
                        QUOTA_HITS.append(time.monotonic())
                        del QUOTA_HITS[:-500]
                    log.warning("%s call failed (attempt %d/%d): %s", self.model, attempt, ATTEMPTS, str(e)[:200])
                    backoff = (1.0 if fg else 3.0) * attempt
                    continue
            finally:
                gate.release()
            from hq.llm import usage
            for r in responses:
                usage.from_response(self.owner, r)
                yield r
            return
        raise last or TimeoutError("model call failed")
