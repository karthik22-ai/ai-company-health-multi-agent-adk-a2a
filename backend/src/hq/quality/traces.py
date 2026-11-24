"""Tracing: every agent run is recorded (who, why, the prompt, each tool call with its arguments and result, tokens, time, outcome),
so any decision or document can be traced back to the data and tools that produced it. Shown in the UI under 📈 Ops."""
from __future__ import annotations

import json
import time
from typing import Any

SCHEMA = """CREATE TABLE IF NOT EXISTS agent_traces(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, sim_date TEXT, agent TEXT, kind TEXT, session TEXT,
            foreground INTEGER, prompt TEXT, reply TEXT, steps TEXT, model_calls INTEGER, prompt_tokens INTEGER, output_tokens INTEGER,
            seconds REAL, status TEXT, error TEXT);
CREATE INDEX IF NOT EXISTS agent_traces_ts ON agent_traces(ts);"""
KEEP = 5000


def _short(x: Any, n: int = 300) -> str:
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    return s if len(s) <= n else s[:n] + "…"


class Trace:
    def __init__(self, agent: str, session: str, prompt: str, foreground: bool):
        self.agent, self.session, self.prompt, self.fg = agent, session, prompt, foreground
        self.t0 = time.time()
        self.steps: list[dict[str, Any]] = []
        self.calls = self.pin = self.pout = 0

    def event(self, ev: Any) -> None:
        try:
            u = getattr(ev, "usage_metadata", None)
            if u is not None:
                self.calls += 1
                self.pin += getattr(u, "prompt_token_count", 0) or 0
                self.pout += (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
            for p in (ev.content.parts if ev.content and ev.content.parts else []):
                if getattr(p, "function_call", None):
                    self.steps.append({"t": round(time.time() - self.t0, 1), "tool": p.function_call.name, "args": _short(dict(p.function_call.args or {}), 400)})
                elif getattr(p, "function_response", None):
                    self.steps.append({"t": round(time.time() - self.t0, 1), "result_of": p.function_response.name,
                                       "result": _short(p.function_response.response, 400)})
        except Exception:  # noqa: BLE001 - tracing must never break a run
            pass

    def finish(self, world: Any, reply: str, error: BaseException | None = None) -> None:
        co = getattr(world, "company", None)
        if co is None:
            return
        try:
            kind = self.session.split("-")[0]
            agent = self.agent.replace("resident_", "").replace("_chat", "")
            agent = agent if agent.startswith("r") and agent[1:].isdigit() else agent.replace("_", ".", 1)
            co.store.db.execute(
                "INSERT INTO agent_traces(ts,sim_date,agent,kind,session,foreground,prompt,reply,steps,model_calls,prompt_tokens,output_tokens,seconds,status,error)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (self.t0, co.today.isoformat(), agent, kind, self.session, int(self.fg), self.prompt[-3000:], (reply or "")[:2000], json.dumps(self.steps[:60]),
                 self.calls, self.pin, self.pout, round(time.time() - self.t0, 2), "error" if error else "ok",
                 f"{type(error).__name__}: {error}"[:300] if error else None))
            co.store.commit()
        except Exception:  # noqa: BLE001
            pass


def ensure(store: Any) -> None:
    store.db.executescript(SCHEMA)
    store.commit()


def list_traces(store: Any, agent: str | None = None, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    q, p = "SELECT id, ts, sim_date, agent, kind, foreground, model_calls, prompt_tokens, output_tokens, seconds, status, error, steps FROM agent_traces WHERE 1=1", []
    if agent:
        q += " AND agent=?"
        p.append(agent)
    if status:
        q += " AND status=?"
        p.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    p.append(limit)
    out = []
    for r in store.rows(q, tuple(p)):
        steps = json.loads(r.pop("steps") or "[]")
        out.append(r | {"tools": [s["tool"] for s in steps if "tool" in s]})
    return out


def get_trace(store: Any, tid: int) -> dict[str, Any] | None:
    r = store.one("SELECT * FROM agent_traces WHERE id=?", (tid,))
    return r | {"steps": json.loads(r["steps"] or "[]")} if r else None


def prune(store: Any) -> None:
    store.db.execute("DELETE FROM agent_traces WHERE id <= (SELECT MAX(id) FROM agent_traces) - ?", (KEEP,))
    store.commit()


def summary(store: Any, minutes: float = 60) -> dict[str, Any]:
    since = time.time() - minutes * 60
    rows = store.rows("SELECT agent, kind, foreground, model_calls, prompt_tokens, output_tokens, seconds, status FROM agent_traces WHERE ts>=?", (since,))
    calls = sum(r["model_calls"] for r in rows)
    fg = [r["seconds"] for r in rows if r["foreground"] and r["status"] == "ok"]
    by_kind: dict[str, dict[str, float]] = {}
    for r in rows:
        k = by_kind.setdefault(r["kind"], {"runs": 0, "errors": 0, "model_calls": 0, "tokens": 0})
        k["runs"] += 1
        k["errors"] += r["status"] != "ok"
        k["model_calls"] += r["model_calls"]
        k["tokens"] += r["prompt_tokens"] + r["output_tokens"]
    top = {}
    for r in rows:
        top[r["agent"]] = top.get(r["agent"], 0) + r["prompt_tokens"] + r["output_tokens"]
    return {"minutes": minutes, "runs": len(rows), "errors": sum(1 for r in rows if r["status"] != "ok"), "model_calls": calls,
            "calls_per_min": round(calls / minutes, 1), "prompt_tokens": sum(r["prompt_tokens"] for r in rows),
            "output_tokens": sum(r["output_tokens"] for r in rows), "chat_avg_s": round(sum(fg) / len(fg), 1) if fg else None,
            "by_kind": by_kind, "top_agents": sorted(top.items(), key=lambda x: -x[1])[:8]}
