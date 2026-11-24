"""Competitors act: every week each rival fund may respond to the market (a price cut, a new-member offer or a brand campaign),
mostly when it is losing members. Their moves change what residents see on the comparison site and are visible to our agents.
Rule-based on purpose: the rivals are the environment, our 51 employees are the agents."""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from typing import Any

MOVES = [
    ("offer", "6 weeks free for new members", 4),
    ("offer", "No waiting periods on extras for switchers", 6),
    ("price", "-3% on hospital and extras for new members", 8),
    ("brand", "TV and social campaign", 4),
]


class Competitors:
    def __init__(self, town: Any):
        self.t = town

    def state(self) -> dict[str, dict[str, Any]]:
        return dict(self.t.store.get_kv("competitor_moves", {}) or {})

    def active(self, d: date | None = None) -> dict[str, dict[str, Any]]:
        d = (d or self.t.co.today).isoformat()
        return {k: v for k, v in self.state().items() if v.get("until", "") >= d}

    def adjust(self, ins: str) -> tuple[float, float, str]:
        """(price multiplier, brand bonus, offer text) for a rival right now."""
        m = self.active().get(ins)
        if not m:
            return 1.0, 0.0, ""
        return (0.97 if m["type"] == "price" else 1.0), (8.0 if m["type"] == "brand" else 0.0), (m["text"] if m["type"] in ("offer", "price") else "")

    def step(self, d: date, rnd: random.Random | None = None) -> list[dict[str, Any]]:
        """Weekly: rivals that lost members in the last 4 weeks are likely to respond; others sometimes do."""
        from hq.town.town import INSURERS, OURS
        rnd = rnd or random.Random(d.toordinal())
        st = self.t.store
        since = (d - timedelta(days=28)).isoformat()
        flows: dict[str, int] = {}
        for e in st.rows("SELECT insurer, data FROM town_events WHERE kind='switch' AND date>=?", (since,)):
            flows[e["insurer"]] = flows.get(e["insurer"], 0) + 1
            before = json.loads(e["data"] or "{}").get("before_insurer")
            if before:
                flows[before] = flows.get(before, 0) - 1
        state, act, out = self.state(), self.active(d), []
        for ins, meta in INSURERS.items():
            if ins == OURS or ins in act:
                continue
            p = .45 if flows.get(ins, 0) < 0 else .1
            if rnd.random() >= p:
                continue
            typ, text, weeks = rnd.choice(MOVES)
            until = (d + timedelta(weeks=weeks)).isoformat()
            state[ins] = {"type": typ, "text": text, "since": d.isoformat(), "until": until, "net_flow_28d": flows.get(ins, 0)}
            ev = self.t.event("", "competitor", f"{meta['name']}: {text} (until {until})", ins, None, state[ins])
            out.append(ev)
        st.set_kv("competitor_moves", state)
        st.commit()
        return out
