"""Health care in Wattle Grove: residents get sick, injured, pregnant or just need check-ups, go to a hospital or clinic, and their fund pays
benefits. AI Company Health owns a private hospital and a clinic: its members pay no gap there and the company's cost is lower (it owns the
facility). Every visit is a claim against the resident's fund; AI Company Health's claims are its claims data.
"""
from __future__ import annotations

import json
import random
from datetime import date
from typing import Any

OURS = "aich"
FACILITIES = {
    "aich_hospital": {"name": "AI Company Health Private Hospital", "owner": OURS, "kinds": {"admission", "surgery", "maternity"}},
    "aich_clinic": {"name": "AI Company Health Clinic", "owner": OURS, "kinds": {"dental", "optical", "physio", "gp"}},
    "hospital": {"name": "Wattle Grove Hospital (public)", "owner": None, "kinds": {"admission", "surgery", "maternity", "emergency"}},
    "clinic": {"name": "Wattle Grove Medical & Dental", "owner": None, "kinds": {"dental", "optical", "physio", "gp"}},
}
# kind: (label, typical cost AUD, which cover pays, daily probability base)
CARE = {
    "gp": ("GP visit", 90, None, .004), "dental": ("dental check-up", 260, "extras", .002), "optical": ("new glasses", 320, "extras", .0008),
    "physio": ("physio session", 95, "extras", .0012), "admission": ("hospital stay", 6500, "hospital", .00015), "surgery": ("knee/hip surgery", 18000, "hospital", .00004),
    "maternity": ("having a baby", 9500, "hospital", 0.0), "emergency": ("emergency (ambulance)", 1300, "hospital", .00008),
}
POOL_CAP = 5000.0   # risk equalisation: above this, most of a hospital claim is shared across all funds (as Australia's Risk Equalisation Trust Fund does)
POOL_KEEP = 0.2     # share of the cost above the cap the fund still carries


def booked(insurer_cost: float, exposure: float = 1.0) -> float:
    """What one town claim costs the fund's books. Visits happen ACCEL times more often than in real life so the town is lively, and a simulated
    day can last longer than planned (the town keeps ticking while agents work), so each visit is booked at its real-world frequency:
    1 / (ACCEL x exposure), exposure = how many planned days of visits that day actually got. Very large claims are pooled (risk equalisation).
    Premiums are real monthly prices."""
    ic = float(insurer_cost or 0)
    return (min(ic, POOL_CAP) + POOL_KEEP * max(0.0, ic - POOL_CAP)) / (ACCEL * max(0.3, float(exposure or 1.0)))


# Australian-style cover rules (indicative): annual extras limits per person and waiting periods for people new to private cover.
# Switchers keep the waiting periods they already served (portability), so these mostly hit new arrivals and young adults buying their first cover.
EXTRAS_LIMIT = {"dental": 800, "optical": 250, "physio": 500}
WAITING_DAYS = {"dental": 60, "optical": 60, "physio": 60, "admission": 60, "surgery": 365, "maternity": 365}
COMPLAIN_GAP = 300          # a gap this big (or a claim refused for a waiting period) may become a complaint to the Ombudsman

TIER_COVER = {"gold": 1.0, "silver": .85, "bronze": .6, "basic": .3}
ACCEL = 6


class Health:
    def __init__(self, town: Any):
        self.t = town
        town.store.db.executescript("""CREATE TABLE IF NOT EXISTS town_claims(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, resident TEXT, insurer TEXT,
                                       kind TEXT, facility TEXT, cost REAL, benefit REAL, gap REAL, insurer_cost REAL);
                                       CREATE TABLE IF NOT EXISTS town_exposure(date TEXT PRIMARY KEY, exposure REAL);""")
        town.store.commit()

    def chance(self, r: dict[str, Any], kind: str) -> float:
        base = CARE[kind][3]
        needs = set(r.get("needs") or [])
        if kind == "dental" and "dental" in needs:
            base *= 2.5
        if kind == "optical" and (r["age"] > 40 or "optical" in needs):
            base *= 2.5
        if kind == "physio" and needs & {"physio", "sports injuries", "chiropractic"}:
            base *= 3
        if kind in ("admission", "emergency"):
            base *= 1 + max(0, r["age"] - 50) / 10
        if kind == "surgery" and "hip & knee" in needs:
            base *= 8
        if kind == "maternity" and "pregnancy" in needs and r.get("gender") == "female" and 22 <= r["age"] <= 42:
            base = .0006
        return base * ACCEL

    def visit(self, r: dict[str, Any], kind: str, d: date, rnd: random.Random | None = None) -> dict[str, Any]:
        """One episode of care: where they go, what it costs, what their fund pays, the gap they pay."""
        rnd = rnd or random.Random()
        cov = r.get("cover") or {}
        ins = cov.get("insurer")
        ours = ins == OURS
        place = ("aich_hospital" if ours and kind in FACILITIES["aich_hospital"]["kinds"] else
                 "aich_clinic" if kind in FACILITIES["aich_clinic"]["kinds"] and (ours or rnd.random() < .25) else
                 "hospital" if kind in FACILITIES["hospital"]["kinds"] else "clinic")
        label, cost, pays, _ = CARE[kind]
        cost = round(cost * rnd.uniform(.8, 1.25))
        if pays == "extras":
            benefit = cost * (.7 if cov.get("extras") else 0)
        elif pays == "hospital":
            frac = TIER_COVER.get(cov.get("tier") or "", 0)
            if kind == "maternity" and cov.get("tier") not in ("gold",):
                frac = 0.0                                      # pregnancy is a Gold-tier clinical category
            if place == "hospital" and kind == "emergency":
                frac = max(frac, .9)                            # public emergency care; ambulance via hospital cover
            benefit = cost * frac * .92
        else:
            benefit = 0.0                                       # GP visits are Medicare (bulk billed), not private health insurance
        if FACILITIES[place]["owner"] == OURS and ours:
            benefit, gap = (cost if pays else 0.0), 0.0         # members: no gap at our own hospital and clinic
            insurer_cost = benefit * .85                        # we own the facility
        else:
            gap = max(0.0, cost - benefit) if pays else (0.0 if rnd.random() < .8 else 40.0)
            insurer_cost = benefit
        note = ""
        if pays and ins and self.waiting(cov, kind, d):
            benefit, insurer_cost, gap, note = 0.0, 0.0, float(cost), " (still in the waiting period: not covered yet)"
        elif pays == "extras" and benefit > 0 and kind in EXTRAS_LIMIT:
            room = max(0.0, EXTRAS_LIMIT[kind] - self.used(r["id"], ins, kind, d))
            if benefit > room:
                share = room / benefit
                gap, insurer_cost, benefit = gap + (benefit - room), insurer_cost * share, room
                note = f" (annual {kind} limit of ${EXTRAS_LIMIT[kind]} reached)"
        benefit, gap, insurer_cost = round(benefit), round(gap), round(insurer_cost)
        self.t.store.db.execute("INSERT INTO town_claims(date,resident,insurer,kind,facility,cost,benefit,gap,insurer_cost) VALUES (?,?,?,?,?,?,?,?,?)",
                                (d.isoformat(), r["id"], ins, kind, place, cost, benefit, gap, insurer_cost))
        self.t.store.commit()
        from hq.town.town import INSURERS
        fund = INSURERS.get(ins, {}).get("name", "no fund")
        text = (f"{r['name']} went to {FACILITIES[place]['name']} for {label}: cost ${cost:,}, {fund} paid ${benefit:,}, gap ${gap:,}"
                + (" (no gap: AI Company Health member)" if FACILITIES[place]["owner"] == OURS and ours and not gap else "") + note)
        e = self.t.event(r["id"], "health", text, ins, None, {"care": kind, "facility": place, "cost": cost, "benefit": benefit, "gap": gap})
        if ins:
            self.aftermath(r, ins, fund, label, gap, bool(note) and "waiting" in note, benefit, rnd)
        return e | {"facility": place, "care": kind, "gap": gap, "benefit": benefit, "cost": cost}

    # ------------------------------------------------------------------ cover rules
    def waiting(self, cov: dict[str, Any], kind: str, d: date) -> bool:
        days = WAITING_DAYS.get(kind, 0)
        if not days or cov.get("transferred", True) or not cov.get("since"):
            return False
        try:
            return (d - date.fromisoformat(cov["since"])).days < days
        except ValueError:
            return False

    def used(self, rid: str, ins: str, kind: str, d: date) -> float:
        row = self.t.store.rows("SELECT SUM(benefit) b FROM town_claims WHERE resident=? AND insurer=? AND kind=? AND date>=?",
                                (rid, ins, kind, f"{d.year}-01-01"))
        return float(row[0]["b"] or 0) if row else 0.0

    def aftermath(self, r: dict[str, Any], ins: str, fund: str, label: str, gap: float, refused: bool, benefit: float, rnd: random.Random) -> None:
        """Experiences travel: a big gap or a refused claim may become a complaint (1-star review); good and bad experiences are told to people
        they know (word of mouth), which residents read when they review their cover."""
        friends = [x for x in self.t.relations(r["id"]) if not x.get("employee") and "passed away" not in x["relation"]]
        if (refused or gap >= COMPLAIN_GAP) and rnd.random() < .3:
            why = "a claim refused in the waiting period" if refused else f"a ${gap:,.0f} gap"
            self.t.review(r["id"], ins, 1, f"Complained to the Private Health Insurance Ombudsman about {why} for {label}.")
            self.t.event(r["id"], "complaint", f"{r['name']} complained to the Ombudsman about {fund}: {why} for {label}", ins)
        if friends and rnd.random() < .35:
            if refused or gap >= 150:
                msg = f"Heads up: {fund} left me ${gap:,.0f} out of pocket for {label}. Check the fine print, maybe avoid them."
            elif benefit > 0 and gap == 0:
                msg = f"{fund} covered my {label} with no gap. Really easy."
            else:
                return
            f = rnd.choice(friends)
            self.t.message(r["id"], f["id"], msg)
            self.t.event(r["id"], "word_of_mouth", f"{r['name']} told {f['name']}: {msg}", ins)

    def tick(self, d: date, fraction: float, rnd: random.Random) -> list[dict[str, Any]]:
        """Episodes of care for a slice of a day (fraction = share of a day this tick represents)."""
        out = []
        self.t.store.db.execute("INSERT INTO town_exposure(date, exposure) VALUES (?, ?) ON CONFLICT(date) DO UPDATE SET exposure = exposure + excluded.exposure",
                                (d.isoformat(), float(fraction)))
        self.t.store.commit()
        for r in self.t.residents():
            for kind in CARE:
                if rnd.random() < self.chance(r, kind) * fraction:
                    out.append(self.visit(r, kind, d, rnd))
                    break
        return out

    def exposure(self, day: str, estimate: bool = False) -> float:
        """Planned days of visits the town actually ran on `day` (1.0 = as planned). Without a record: 1.0, or with estimate=True a guess from
        how many visits happened that day compared with the expected number (for days recorded before exposure was tracked)."""
        row = self.t.store.rows("SELECT exposure FROM town_exposure WHERE date=?", (day,))
        if row and row[0]["exposure"]:
            return float(row[0]["exposure"])
        if not estimate:
            return 1.0
        expected = sum(self.chance(r, k) for r in self.t.residents() for k in CARE)
        seen = self.t.store.rows("SELECT COUNT(*) n FROM town_claims WHERE date=?", (day,))[0]["n"]
        return max(0.3, min(10.0, seen / expected)) if expected and seen else 1.0

    def booked_cost(self, insurer: str, day: str, estimate: bool = False) -> float:
        x = self.exposure(day, estimate)
        return sum(booked(c["insurer_cost"], x) for c in self.t.store.rows("SELECT insurer_cost FROM town_claims WHERE date=? AND insurer=?", (day, insurer)))

    def claims(self, rid: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        if rid:
            return self.t.store.rows("SELECT * FROM town_claims WHERE resident=? ORDER BY id DESC LIMIT ?", (rid, limit))
        return self.t.store.rows("SELECT * FROM town_claims ORDER BY id DESC LIMIT ?", (limit,))

    def summary(self, insurer: str = OURS, since: str = "") -> dict[str, Any]:
        rows = self.t.store.rows("SELECT kind, facility, COUNT(*) n, SUM(cost) cost, SUM(benefit) benefit, SUM(gap) gap, SUM(insurer_cost) ic FROM town_claims "
                                 "WHERE insurer=? AND date>=? GROUP BY kind, facility", (insurer, since))
        return {"by_kind_and_facility": rows, "claims": sum(r["n"] for r in rows), "benefits_paid": sum(r["benefit"] or 0 for r in rows),
                "members_gap": sum(r["gap"] or 0 for r in rows), "cost_to_insurer": sum(r["ic"] or 0 for r in rows),
                "booked_claims_cost": round(sum(self.booked_cost(insurer, x["date"]) for x in self.t.store.rows(
                    "SELECT DISTINCT date FROM town_claims WHERE insurer=? AND date>=?", (insurer, since))), 2),
                "note": f"Visits happen {ACCEL}x more often than in real life so the town is lively; the books count each at its real frequency "
                        f"and hospital claims above ${POOL_CAP:,.0f} are mostly pooled across funds (risk equalisation). Use booked_claims_cost for loss ratios."}


def _unused() -> str:
    return json.dumps({})
