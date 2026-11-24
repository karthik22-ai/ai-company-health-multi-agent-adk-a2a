"""Event bus: every UI command goes through here, is persisted, and fanned out to WebSocket/SSE clients."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from pathlib import Path
from typing import Any

log = logging.getLogger("hq.core.bus")


class EventLog:
    """Append-only JSONL audit log of everything sent to the UI."""

    def __init__(self, path: Path | None):
        self.path = path
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, cmd: dict[str, Any]) -> None:
        if not self.path:
            return
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), **cmd}, ensure_ascii=False) + "\n")
        except OSError as e:  # never break the live system because of the audit log
            log.warning("event log write failed: %s", e)

    def tail(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.path or not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return out


class EventBus:
    def __init__(self, event_log: EventLog | None = None, history: int = 500):
        self._subs: set[asyncio.Queue] = set()
        self.history: deque[dict[str, Any]] = deque(maxlen=history)
        self.event_log = event_log or EventLog(None)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def publish(self, cmd: dict[str, Any]) -> None:
        self.history.append(cmd)
        self.event_log.append(cmd)
        for q in list(self._subs):
            try:
                q.put_nowait(cmd)
            except asyncio.QueueFull:  # slow client: drop oldest
                try:
                    q.get_nowait()
                    q.put_nowait(cmd)
                except Exception:  # pragma: no cover
                    pass
