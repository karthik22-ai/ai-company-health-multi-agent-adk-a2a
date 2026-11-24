"""The town loop: Wattle Grove lives continuously, independent of the company's (slower) workflows.

Every few seconds: residents follow their day plan, some need health care (and go to a hospital or clinic; their fund pays a claim),
and a few residents with a reason review their health insurance (their own AI agent decides; rule-based when the agents are switched off).
Reasons come from life: a big gap bill, the 1 April premium notice, an ad, a friend's message, a new baby, a new job...
"""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import date
from typing import Any

log = logging.getLogger("hq.town.loop")


def day_plan(r: dict[str, Any], d: date, town: Any) -> list[dict[str, str]]:
    """What a resident does today, from their age, job, hobbies, personality and relations (times are 24h)."""
    rnd = random.Random(f"{r['id']}-{d.isoformat()}")
    weekend = d.weekday() >= 5
    built = {f["kind"] for f in town.life.facilities()}
    hob = r.get("hobbies") or []
    friends = [x for x in town.relations(r["id"]) if not x.get("employee") and x["relation"] in ("friend", "gym buddy", "work colleague") and not x.get("deceased")]
    plan: list[dict[str, str]] = [{"t": "06:30", "place": "home", "label": "Wakes up at home"}]
    leisure = []
    if any(h in hob for h in ("going to the gym", "yoga")):
        leisure.append(("gym" if "gym" in built else "mall", "Workout at FitGrove Gym" if "gym" in built else "Yoga class at the mall"))
    if any(h in hob for h in ("running", "cycling", "footy", "gardening")) or r["age"] < 13:
        leisure.append(("park" if "park" in built else "home", "At Wattle Grove Park" if "park" in built else ("Gardening at home" if "gardening" in hob else "Exercise around the block")))
    if friends:
        f = rnd.choice(friends)
        leisure.append((f"friend:{f['id']}", f"Visits {f['name'].split()[0]} ({f['relation']})"))
    leisure += [("mall", "Shopping at Wattle Grove Mall"), ("cafe", "Coffee on High Street")]
    if r["age"] < 5:
        plan += [{"t": "08:00", "place": "fac_childcare" if "childcare" in built else "home", "label": "At childcare" if "childcare" in built else "Playing at home"},
                 {"t": "16:00", "place": "home", "label": "Home with family"}]
    elif r["age"] < 18:
        if not weekend:
            plan += [{"t": "08:15", "place": "school", "label": "Off to Wattle Grove Public School"}, {"t": "15:15", "place": "home", "label": "Home from school"}]
        a = rnd.choice(leisure)
        plan.append({"t": "16:30" if not weekend else "10:30", "place": a[0], "label": a[1]})
    elif r.get("workplace") in (None, "home") or weekend:
        a, b = rnd.sample(leisure, 2) if len(leisure) > 1 else (leisure[0], leisure[0])
        plan += [{"t": "09:30", "place": a[0], "label": a[1]}, {"t": "12:30", "place": "cafe", "label": "Lunch on High Street"}, {"t": "14:30", "place": b[0], "label": b[1]}]
    else:
        how = r.get("vehicle") or "car"
        plan += [{"t": "07:45", "place": "work", "label": f"{'Drives' if 'bus' not in how and 'walk' not in how and 'bike' not in how and 'bicycle' not in how else 'Commutes'} to work at {r.get('employer', 'work')}"},
                 {"t": "12:30", "place": "cafe" if r.get("workplace") != "cafe" else "work", "label": "Lunch break"},
                 {"t": "13:15", "place": "work", "label": f"Back at {r.get('employer', 'work')}"}]
        if rnd.random() < .6:
            a = rnd.choice(leisure)
            plan.append({"t": "17:30", "place": a[0], "label": a[1]})
    plan.append({"t": "19:00", "place": "home", "label": "Dinner at home"})
    return plan


class TownLoop:
    def __init__(self, svc: Any):
        self.svc = svc
        self.queue: list[dict[str, str]] = []
        self.busy: set[str] = set()
        self.plan_date: str | None = None
        self.credit = 0.0
        self.rnd = random.Random(7)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._run(), name="town-loop")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    def nudge(self, rid: str, reason: str) -> None:
        if rid not in self.busy and not any(q["resident"] == rid for q in self.queue):
            self.queue.append({"resident": rid, "reason": reason})

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.svc.settings.town_tick_seconds)
            r = self.svc.runner
            if not r or not (r.running or r.busy):
                continue
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - the town keeps living
                log.exception("town tick failed")

    def plans(self) -> dict[str, list]:
        co = self.svc.company
        return {r["id"]: day_plan(r, co.today, co.town) for r in co.town.residents()}

    async def tick(self) -> None:
        co, w, town = self.svc.company, self.svc.world, self.svc.company.town
        s = self.svc.settings
        d = co.today
        if self.plan_date != d.isoformat():                              # a new day: plans, and who has a reason to review their cover
            self.plan_date = d.isoformat()
            w.emit({"type": "town_plans", "date": self.plan_date, "plans": self.plans()})
            for t in town.triggers(d, 12):
                self.nudge(t["resident"], t["reason"])
        frac = s.town_tick_seconds / max(60.0, self.svc.runner.seconds_per_day)
        for v in town.health.tick(d, frac, self.rnd):                    # health care
            r = town.resident(v["resident"]) or {}
            w.emit({"type": "town_visit", "event": {k: v.get(k) for k in ("id", "date", "resident", "kind", "insurer", "text")}, "facility": v["facility"],
                    "care": v["care"], "gap": v["gap"]})
            w.remember(v["resident"], "health", v["text"], .7 if v["gap"] > 150 else .4)
            if v["gap"] > 150 and (r.get("cover") or {}).get("insurer") != "aich":
                self.nudge(v["resident"], f"You just paid a ${v['gap']:,} gap at {v['facility'].replace('_', ' ')} for {v['care']} - you're annoyed and wondering if another fund is better.")
                if self.rnd.random() < .35:
                    town.review(v["resident"], r["cover"]["insurer"], 2, f"Paid a ${v['gap']:,} gap for {v['care']}. Not happy.")
            elif v["gap"] == 0 and v["facility"].startswith("aich") and self.rnd.random() < .35:
                town.review(v["resident"], "aich", 5, f"No gap for {v['care']} at the AI Company Health {'hospital' if 'hospital' in v['facility'] else 'clinic'}. Great.")
        self.credit += s.town_decisions_per_minute * s.town_tick_seconds / 60.0   # insurance decisions, a few at a time
        while self.credit >= 1 and self.queue and len(self.busy) < 2:
            self.credit -= 1
            q = self.queue.pop(0)
            self.busy.add(q["resident"])
            asyncio.create_task(self._decide(q["resident"], q["reason"]), name=f"decide-{q['resident']}")
        self.credit = min(self.credit, 3.0)

    async def _decide(self, rid: str, reason: str) -> None:
        w, town = self.svc.world, self.svc.company.town
        try:
            w.emit({"type": "town_shoppers", "shoppers": [{"resident": rid, "reason": reason}]})
            if self.svc.runner.agents:
                await self.svc.runtime.run_resident(rid, reason)             # the resident's own AI agent decides
            else:
                from hq.town.town import mock_choice
                r = town.resident(rid)
                prof = dict(r, mls_if_no_hospital=town.mls(r))
                choice, why = mock_choice(town, prof, town.comparison(r), town.feed(rid))
                ev = town.keep(rid, why) if choice in (None, "keep") else town.buy(rid, choice, why)
                if "error" not in ev:
                    w.emit({"type": "town_event", "event": ev, "say": "🛒 " + (ev.get("insurer") or "") if ev["kind"] != "keep" else "🤔 Keeping my cover"})
                    w.remember(rid, "decision", ev["text"], .8)
        finally:
            self.busy.discard(rid)
