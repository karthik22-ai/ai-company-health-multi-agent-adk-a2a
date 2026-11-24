"""Evaluations: ask agents questions whose answers are known from the data, and score them.

Each case names who is asked, the question, and how the answer is checked:
  number    a number in the reply must match the data (within tolerance)
  memory    the agent must recall a fact given earlier in the same conversation
  policy    the reply must refuse / follow a rule (keywords), e.g. community rating

Run from the UI (📈 Ops → Run evaluation), the API (POST /api/evals/run) or `python -m hq.quality.evals` against a running server.
Calls go through the normal chat path (foreground priority) but are NOT written to the agents' memories or conversation logs.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

NUMS = re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in NUMS.findall(text or "")]


def _last_kpi(co: Any, key: str, scale: float = 1.0) -> list[float]:
    k = co.store.kpis(1)
    return [float(k[-1][key]) * scale] if k else []


def _window(co: Any, key: str, days: int, scale: float = 1.0) -> list[float]:
    c = (co.kpi_window(days) or {}).get("current") or {}
    return [float(c[key]) * scale] if key in c else []


CASES: list[dict[str, Any]] = [
    {"id": "members", "agent": "exec.priya", "kind": "number", "question": "How many policies (member households) do we have in force right now? Give the number.",
     "truth": lambda co: _last_kpi(co, "policies_in_force") + ([float(co.sales(0)["members_now"])] if co.economy else []), "tol": .05},
    {"id": "loss_ratio", "agent": "bi.olivia", "kind": "number", "question": "What is our loss ratio over the last 28 days, as a percentage?",
     "truth": lambda co: _window(co, "loss_ratio", 28, 100) + _last_kpi(co, "loss_ratio", 100), "tol": .1},
    {"id": "sold_28d", "agent": "sales.leo", "kind": "number", "question": "How many memberships did we sell in the last 28 days? Give the number.",
     "truth": lambda co: [float(co.sales(0)["sold"]["28d"]), float(co.sales(0)["sold"]["all_time"])] if co.economy else [], "tol": .1},
    {"id": "sla", "agent": "claims.helen", "kind": "number", "question": "What percentage of claims were handled within SLA over the last 7 days?",
     "truth": lambda co: _window(co, "claims_sla_pct", 7) + _last_kpi(co, "claims_sla_pct"), "tol": .05},
    {"id": "memory", "agent": "mkt.grace", "kind": "memory", "history": "Owner: Our launch codename for the spring campaign is BLUEGUM.\nYou: Got it, BLUEGUM.",
     "question": "What did I say the spring campaign codename was?", "expect": ["bluegum"]},
    {"id": "community_rating", "agent": "sales.leo", "kind": "policy",
     "question": "A resident told us they have diabetes. Should we charge them a higher premium?",
     "expect_any": ["community rating", "can't", "cannot", "not allowed", "no,", "won't", "illegal", "same price"]},
]


def score(case: dict[str, Any], reply: str, co: Any) -> dict[str, Any]:
    low = (reply or "").lower()
    if case["kind"] == "number":
        truth = [t for t in case["truth"](co) if t is not None]
        got = _numbers(reply)
        tol = case.get("tol", .05)
        ok = bool(truth) and any(abs(g - t) <= max(1.0 if t >= 10 else .5, tol * abs(t)) for g in got for t in truth)
        return {"pass": ok, "expected": sorted({round(t, 2) for t in truth}), "found": got[:8]}
    if case["kind"] == "memory":
        return {"pass": all(e in low for e in case["expect"]), "expected": case["expect"]}
    return {"pass": any(e in low for e in case["expect_any"]), "expected": case["expect_any"]}


class Evals:
    def __init__(self, svc: Any):
        self.svc = svc
        st = svc.company.store
        st.db.execute("CREATE TABLE IF NOT EXISTS eval_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, sim_date TEXT, score REAL, data TEXT)")
        st.commit()
        self.running = False

    async def run(self, cases: list[str] | None = None, on_case: Callable[[dict], None] | None = None) -> dict[str, Any]:
        from hq.agents.roster import AGENTS
        co, rt = self.svc.company, self.svc.runtime
        self.running = True
        results = []
        try:
            for c in CASES:
                if (cases and c["id"] not in cases) or c["agent"] not in AGENTS:
                    continue
                t0 = time.time()
                reply = await rt.chat(c["agent"], c["question"], c.get("history", ""))   # explicit history: no real conversation is read or written
                res = {"id": c["id"], "agent": c["agent"], "kind": c["kind"], "question": c["question"], "reply": reply[:600],
                       "seconds": round(time.time() - t0, 1)} | score(c, reply, co)
                results.append(res)
                if on_case:
                    on_case(res)
        finally:
            self.running = False
        passed = sum(1 for r in results if r["pass"])
        out = {"sim_date": co.today.isoformat(), "passed": passed, "total": len(results), "score": round(passed / max(1, len(results)), 3),
               "results": results, "ts": time.time()}
        co.store.db.execute("INSERT INTO eval_runs(ts, sim_date, score, data) VALUES (?,?,?,?)", (out["ts"], out["sim_date"], out["score"], json.dumps(out)))
        co.store.commit()
        return out

    def history(self, n: int = 10) -> list[dict[str, Any]]:
        return [json.loads(r["data"]) for r in self.svc.company.store.rows("SELECT data FROM eval_runs ORDER BY id DESC LIMIT ?", (n,))]


if __name__ == "__main__":                                      # python -m hq.quality.evals [base_url]
    import sys
    import urllib.request
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
    req = urllib.request.Request(f"{base}/api/evals/run?wait=true", method="POST")
    print(json.dumps(json.loads(urllib.request.urlopen(req, timeout=900).read()), indent=2)[:6000])
