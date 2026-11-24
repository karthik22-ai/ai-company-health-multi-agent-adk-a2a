"""The daily simulation of the health insurer: demand, sales, cancellations, claims, service levels, staffing and money.

`CompanySim.step(day)` advances one day deterministically from (seed, date, state). Strategic initiatives, hiring, pricing and market
events change the levers; results are written to SQLite (`Store`) and returned as a `DayResult`.
"""
from __future__ import annotations

import copy
import json
import zlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np

from hq.company import initiatives as ini_mod
from hq.company.catalog import (
    AGE_BANDS,
    BASE_ANNUAL_ATTRITION,
    BASE_MARKETING_DAILY,
    CALLS_PER_POLICY_DAY,
    CARE_CAPACITY_DOW,
    CHANNELS,
    CLAIMS_CAPACITY_DOW,
    DEPT_COSTS,
    DOW_CALLS,
    DOW_CLAIMS,
    DOW_SALES,
    FIXED_OPEX_DAILY,
    INVESTMENT_YIELD,
    MONTH_SALES,
    OPENING_POLICIES,
    PRODUCTS,
    STATES,
    VARIABLE_EXPENSE,
    Product,
    industry_rate_rise,
)
from hq.company.store import Store

CLAIM_TYPE_MIX = {            # share of benefits by claim type, per product category
    "hospital": {"hospital_admission": 1.0},
    "extras": {"dental": .50, "optical": .20, "physio": .20, "other_extras": .10},
    "combined": {"hospital_admission": .62, "dental": .16, "optical": .08, "physio": .08, "other_extras": .06},
    "ambulance": {"ambulance": 1.0},
    "ovhc": {"hospital_admission": .80, "medical": .20},
    "oshc": {"medical": .70, "hospital_admission": .30},
}
CLAIM_AVG = {"hospital_admission": 4200, "dental": 135, "optical": 180, "physio": 75, "other_extras": 110, "ambulance": 480, "medical": 190}
CLAIM_FOCUS = {"hospital_admission": "hospital", "dental": "dental", "optical": "optical", "physio": "physio", "other_extras": "extras"}
CLAIMS_CALIBRATION = 0.955     # scales plan claims ratios so the blended, seasonal loss ratio sits near 86-87%
CANCEL_REASONS = ["price", "service", "no_longer_needed", "switched_insurer", "moved_overseas"]

EVENT_TEMPLATES: list[dict[str, Any]] = [
    {"type": "competitor_promo", "name": "Competitor cashback promotion", "days": (10, 20), "p": 0.9, "fx": {"conv_mult": 0.88, "lapse_mult": 1.08},
     "desc": "A large competitor is advertising cashback for switchers."},
    {"type": "comparison_outage", "name": "Comparison-site outage", "days": (2, 4), "p": 0.6, "fx": {"leads_mult_comparison_site": 0.25},
     "desc": "A major comparison site is down; lead flow from it has collapsed."},
    {"type": "flu_outbreak", "name": "Flu outbreak", "days": (14, 24), "p": 0.9, "fx": {"claims_mult": 1.07, "calls_mult": 1.12}, "season": (5, 9),
     "desc": "A strong flu season is lifting hospital admissions and calls."},
    {"type": "positive_media", "name": "Positive media coverage", "days": (5, 9), "p": 0.7, "fx": {"conv_mult": 1.06, "brand": 2.5},
     "desc": "A consumer magazine rated our hospital cover best value."},
    {"type": "negative_media", "name": "Negative media story", "days": (7, 12), "p": 0.7, "fx": {"conv_mult": 0.94, "nps": -2.0, "lapse_mult": 1.08},
     "desc": "A news story criticises health-fund premium rises and claims delays."},
    {"type": "web_outage", "name": "Website and quote-engine outage", "days": (1, 3), "p": 0.5, "fx": {"leads_mult_online_direct": 0.45, "conv_mult": 0.92},
     "desc": "Online quotes were unavailable for part of the day."},
    {"type": "regulatory_change", "name": "Regulatory change announced", "days": (8, 14), "p": 0.5, "fx": {"calls_mult": 1.10},
     "desc": "New government rules are prompting member questions."},
    {"type": "hospital_dispute", "name": "Hospital contract dispute", "days": (10, 20), "p": 0.5, "fx": {"claims_mult": 1.05, "nps": -1.0},
     "desc": "A private hospital group dispute is causing gap-payment complaints."},
]


@dataclass
class DayResult:
    date: str
    kpi: dict[str, Any]
    events_started: list[dict[str, Any]] = field(default_factory=list)
    scheduled: list[str] = field(default_factory=list)       # human-readable things that happened today (launches, hires, rises)


def dow(d: date) -> int:
    return d.weekday()


class CompanySim:
    def __init__(self, store: Store, seed: int = 7, start: date = date(2026, 3, 2)):
        self.store, self.seed, self.start = store, seed, start
        self.products: dict[str, Product] = {p.id: copy.deepcopy(p) for p in PRODUCTS}
        self.s: dict[str, Any] = {}
        self.initiatives: dict[str, dict[str, Any]] = {}
        self._pending_launch: list[dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------ state
    def _fresh_state(self, first: date) -> dict[str, Any]:
        inf = {p.id: OPENING_POLICIES * p.start_share for p in self.products.values()}
        inf_state = {st: OPENING_POLICIES * w / sum(STATES.values()) for st, w in STATES.items()}
        team = {d: {"staff": float(c.headcount), "ramp": [], "pipeline": [], "engagement": 69.0, "exits_acc": 0.0, "util": 0.9, "prod": 1.0}
                for d, c in DEPT_COSTS.items()}
        return {"date": (first - timedelta(days=1)).isoformat(), "in_force": inf, "in_force_state": inf_state,
                "price_idx": {p: 1.0 for p in self.products}, "market_idx": 1.0, "brand": 42.0, "nps": 24.0, "backlog": 3500.0,
                "team": team, "promo_pool": 0.0, "price_shock": 0.0, "events": [], "pending_prices": [],
                "budget": {"fy_year": first.year if first.month >= 7 else first.year - 1, "remaining": 24_000_000.0},
                "csat": 80.0, "days": 0}

    def _load(self) -> None:
        s = self.store.get_kv("sim_state")
        self.s = s if s else self._fresh_state(self.start)
        for d, c in DEPT_COSTS.items():          # states saved before a department existed
            self.s["team"].setdefault(d, {"staff": float(c.headcount), "ramp": [], "pipeline": [], "engagement": 69.0, "exits_acc": 0.0,
                                          "util": 0.9, "prod": 1.0})
        self._pending_launch = self.store.get_kv("pending_launch", [])
        for row in self.store.rows("SELECT * FROM initiatives"):
            d = json.loads(row["data"])
            self.initiatives[row["id"]] = d
        for pid, p in json.loads(json.dumps(self.store.get_kv("custom_products", {}))).items():
            self.products[pid] = Product(**p)

    def save(self) -> None:
        self.store.set_kv("sim_state", self.s)

    @property
    def today(self) -> date:
        return date.fromisoformat(self.s["date"])

    # ------------------------------------------------------------------ context for estimates / agents
    def context(self) -> dict[str, Any]:
        sales_pd = {p: 0.0 for p in self.products}
        rows = self.store.rows("SELECT product_id, SUM(sales) n FROM daily_sales WHERE date > date(?, '-28 day') GROUP BY product_id", (self.s["date"],))
        for r in rows:
            sales_pd[r["product_id"]] = r["n"] / 28
        return {"sales_per_day": sales_pd, "headcount": {d: t["staff"] for d, t in self.s["team"].items()}, "date": self.s["date"]}

    # ------------------------------------------------------------------ initiatives (scheduling)
    def schedule(self, ini: dict[str, Any], decided: date) -> None:
        """An approved initiative gets a start date, an end date and a hidden realised-effect factor."""
        rng = np.random.default_rng([self.seed, 99, zlib.crc32(ini["id"].encode()) % 10_000_000])
        kind, p = ini["kind"], ini["params"]
        ini["start_date"] = (decided + timedelta(days=ini_mod.LEAD_DAYS[kind] + int(rng.integers(0, 4)))).isoformat()
        dur = ini_mod.duration_days(kind, p)
        ini["end_date"] = (date.fromisoformat(ini["start_date"]) + timedelta(days=dur)).isoformat() if dur else None
        ini["realised"] = ini_mod.realise(kind, rng)
        if kind == "hire":
            arrive = decided + timedelta(days=int(rng.integers(32, 58)))
            self.s["team"][p["dept"]]["pipeline"].append([p["count"], arrive.isoformat(), ini["id"]])
        if kind == "new_product":
            self._pending_launch.append({"id": ini["id"], "date": ini["start_date"]})
        ini["status"] = "approved"
        self.store.set_kv("pending_launch", self._pending_launch)

    # ------------------------------------------------------------------ pricing
    def schedule_price_changes(self, changes: dict[str, float], effective: date) -> None:
        self.s["pending_prices"].append({"effective": effective.isoformat(), "changes": changes})

    # ------------------------------------------------------------------ the day
    def step(self, d: date, *, persist: bool = True, history: bool = False) -> DayResult:
        s = self.s
        rng = np.random.default_rng([self.seed, d.toordinal()])
        notes: list[str] = []
        started: list[dict[str, Any]] = []

        # --- calendar events -------------------------------------------------
        fx_prices = [x for x in s["pending_prices"] if x["effective"] == d.isoformat()]
        if d.month == 4 and d.day == 1:
            rise = industry_rate_rise(d.year) + float(rng.normal(0, 0.003))
            s["market_idx"] *= 1 + rise
            if history:                                    # in the pre-history we followed the market on 1 April
                for pid in s["price_idx"]:
                    s["price_idx"][pid] *= 1 + rise * 0.97
            s["price_shock"] += 2.2
            notes.append(f"1 April: industry premium round (+{rise*100:.2f}% market)")
            started.append(self._event(d, "premium_round", "Annual premium round", f"Industry premiums rose about {rise*100:.1f}% today.",
                                       {"calls_mult": 1.35, "lapse_mult": 1.12}, 14))
        for x in fx_prices:
            for pid, c in x["changes"].items():
                if pid in s["price_idx"]:
                    s["price_idx"][pid] *= 1 + c
            avg = np.mean(list(x["changes"].values())) if x["changes"] else 0
            s["price_shock"] += max(0.0, (avg - 0.02) * 40)
            notes.append(f"Our premium round took effect (avg {avg*100:+.2f}%)")
            s["pending_prices"].remove(x)
        # random events
        s["events"] = [e for e in s["events"] if e["end"] >= d.isoformat()]
        if rng.random() < 0.035:
            t = EVENT_TEMPLATES[int(rng.integers(0, len(EVENT_TEMPLATES)))]
            in_season = "season" not in t or t["season"][0] <= d.month <= t["season"][1]
            if in_season and not any(e["type"] == t["type"] for e in s["events"]) and rng.random() < t["p"]:
                started.append(self._event(d, t["type"], t["name"], t["desc"], t["fx"], int(rng.integers(*t["days"]))))
        for e in started:
            if e not in s["events"]:
                s["events"].append(e)
        fx = self._effects(s["events"])

        # --- launches / hires arrive -----------------------------------------
        for pl in list(self._pending_launch):
            if pl["date"] <= d.isoformat():
                notes.append(self._launch(pl["id"], d))
                self._pending_launch.remove(pl)
        cost_one_off = 0.0
        for dept, t in s["team"].items():
            for item in list(t["pipeline"]):
                if item[1] <= d.isoformat():
                    t["staff"] += item[0]
                    t["ramp"].append([item[0], d.isoformat()])
                    cost_one_off += item[0] * DEPT_COSTS[dept].salary * 0.12 if str(item[2]).startswith("I") else 0.0
                    notes.append(f"{item[0]} new starter(s) joined {dept}")
                    t["pipeline"].remove(item)

        # --- levers from running initiatives ---------------------------------
        ctx = {"headcount": {k: v["staff"] for k, v in s["team"].items()}}
        lv = ini_mod.Levers()
        for ini in self.initiatives.values():
            if ini["status"] in ("approved", "running", "completed") and ini.get("start_date"):
                ini_mod.levers_for(ini, d, lv, ctx)
        self._update_initiative_status(d)

        # --- team capacity -----------------------------------------------------
        eff_staff, prod = {}, {}
        for dept, t in s["team"].items():
            ramp_loss = 0.0
            keep = []
            for n, hired in t["ramp"]:
                age = (d - date.fromisoformat(hired)).days
                if age < 60:
                    ramp_loss += n * (1 - min(1.0, 0.3 + 0.7 * age / 60))
                    keep.append([n, hired])
            t["ramp"] = keep
            eff_staff[dept] = max(t["staff"] - ramp_loss, 1.0)
            prod[dept] = lv.prod_mult.get(dept, 1.0)
            t["prod"] = round(prod[dept] * (eff_staff[dept] / max(t["staff"], 1)), 4)

        # --- demand, sales ----------------------------------------------------------
        season = MONTH_SALES[d.month - 1] * DOW_SALES[dow(d)]
        if d.month == 6 and d.day >= 20:
            season *= 1.25
        if d.month == 3 and d.day >= 18:
            season *= 1.12
        if d.month == 4 and d.day <= 7:
            season *= 0.90
        brand_factor = 1 + (s["brand"] - 42) / 100 * 0.6
        rel = {pid: (s["price_idx"][pid] / s["market_idx"]) for pid in self.products}
        w = {pid: p.sales_share * lv.product_weight.get(pid, 1.0) * rel[pid] ** -1.8 * (p.active and 1 or 0) for pid, p in self.products.items()}
        wsum = sum(w.values()) or 1.0
        wn = np.array([w[pid] / wsum for pid in self.products])
        price_conv = float(sum(self.products[pid].sales_share * rel[pid] ** -1.2 for pid in self.products) / sum(p.sales_share for p in self.products.values()))
        nps_factor = 1 + (s["nps"] - 24) / 300
        conv_global = lv.conv_mult * fx.get("conv_mult", 1.0) * price_conv * nps_factor

        leads: dict[str, int] = {}
        for cid, ch in CHANNELS.items():
            lam = ch.base_leads * season * brand_factor * fx.get(f"leads_mult_{cid}", 1.0) * lv.leads_mult.get(cid, 1.0) + lv.extra_leads.get(cid, 0.0) * (0.35 + 0.65 * min(season, 1.2))
            lam *= float(rng.gamma(60, 1 / 60))
            leads[cid] = int(rng.poisson(max(lam, 0)))
        phone_leads = sum(leads[c] for c, ch in CHANNELS.items() if ch.phone)
        weekday_cap = 1.0 if dow(d) < 5 else (0.3 if dow(d) == 5 else 0.15)
        sales_cap = eff_staff["sales"] * 0.6 * DEPT_COSTS["sales"].productivity * prod["sales"] * weekday_cap
        sales_util = phone_leads / max(sales_cap, 1.0)
        handled = min(1.0, 1.0 / sales_util) if sales_util > 1 else 1.0
        sales_by_channel: dict[str, int] = {}
        conv_by_channel: dict[str, float] = {}
        for cid, ch in CHANNELS.items():
            conv = ch.conv * conv_global * (handled if ch.phone else 1.0)
            conv_by_channel[cid] = min(conv, 0.6)
            sales_by_channel[cid] = int(rng.binomial(leads[cid], conv_by_channel[cid]))
        state_p = np.array(list(STATES.values())) / sum(STATES.values())
        pids = list(self.products)
        sales_rows, prod_sales = [], {pid: 0 for pid in pids}
        promo_new = 0.0
        for cid, n in sales_by_channel.items():
            if n <= 0:
                continue
            per_prod = rng.multinomial(n, wn)
            for pid, c in zip(pids, per_prod):
                if c <= 0:
                    continue
                prod_sales[pid] += int(c)
                per_state = rng.multinomial(int(c), state_p)
                price_pa = self.products[pid].price * s["price_idx"][pid] * 12
                disc = lv.promo_discount.get(pid, 0.0)
                for st, k in zip(STATES, per_state):
                    if k > 0:
                        sales_rows.append((d.isoformat(), st, cid, pid, int(k), round(k * price_pa * (1 - disc), 2)))
                        s["in_force_state"][st] += int(k)
                if disc:
                    promo_new += c * price_pa * disc
        age_rows = []
        for pid, c in prod_sales.items():
            if c > 0:
                mix = np.array(self.products[pid].age_mix, dtype=float)
                mix = mix / mix.sum() if mix.sum() else np.ones(len(AGE_BANDS)) / len(AGE_BANDS)
                for band, k in zip(AGE_BANDS, rng.multinomial(c, mix)):
                    if k > 0:
                        age_rows.append((d.isoformat(), pid, band, int(k)))
        s["promo_pool"] = s["promo_pool"] * (1 - 0.0004) + promo_new
        total_sales = sum(prod_sales.values())

        # --- service levels (computed first: they drive cancellations and NPS) --------------
        claims_rows, arrivals, benefits_total, prem_total, book_rows = [], 0.0, 0.0, 0.0, []
        trend = 1 + 0.00011 * s["days"]
        in_force_total = sum(s["in_force"].values())
        claims_by_type_count: dict[str, float] = {}
        paid_by_type: dict[str, float] = {}
        for pid, p in self.products.items():
            n = s["in_force"][pid]
            prem = n * p.price * s["price_idx"][pid] * 12 / 365
            prem_total += prem
            cat = p.category
            sea = 1.0
            if cat in ("hospital", "combined", "ovhc") and d.month in (6, 7, 8):
                sea = 1.07
            if cat in ("extras", "combined") and d.month in (11, 12):
                sea = 1.18
            if d.month == 1:
                sea *= 0.82 if cat in ("extras", "combined") else 0.95
            m = fx.get("claims_mult", 1.0) * trend * sea * float(rng.lognormal(0, 0.04))
            paid_cat = prem * p.claims_ratio * CLAIMS_CALIBRATION * m
            for ctype, share in CLAIM_TYPE_MIX[cat].items():
                focus = CLAIM_FOCUS.get(ctype, "extras")
                cm = lv.claims_mult.get(focus, 1.0) * (lv.claims_mult.get("extras", 1.0) if focus in ("dental", "optical", "physio") else 1.0)
                paid = paid_cat * share * cm
                paid_by_type[ctype] = paid_by_type.get(ctype, 0.0) + paid
            book_rows.append((d.isoformat(), pid, round(n, 1), round(prem, 2)))
            benefits_total += paid_cat
        # claims arrivals follow the weekly rhythm (benefits accrue smoothly)
        dow_f = DOW_CLAIMS[dow(d)] / (sum(DOW_CLAIMS) / 7)
        for ctype, paid in paid_by_type.items():
            cnt = paid / CLAIM_AVG[ctype]
            claims_by_type_count[ctype] = cnt
        arr_state = state_p
        for ctype, cnt in claims_by_type_count.items():
            n_arr = int(rng.poisson(max(cnt * dow_f, 0)))
            arrivals += n_arr
            if n_arr > 0:
                per_state = rng.multinomial(n_arr, arr_state)
                for st, k in zip(STATES, per_state):
                    if k > 0:
                        claims_rows.append((d.isoformat(), st, ctype, int(k), round(paid_by_type[ctype] * k / n_arr, 2)))
        # claims processing
        cap_dow = CLAIMS_CAPACITY_DOW[dow(d)]
        claims_cap = eff_staff["claims"] * DEPT_COSTS["claims"].productivity * prod["claims"] * cap_dow * float(rng.normal(1.0, 0.03))
        weekday_cap_claims = eff_staff["claims"] * DEPT_COSTS["claims"].productivity * prod["claims"]
        avail = s["backlog"] + arrivals
        processed = min(avail, claims_cap)
        s["backlog"] = avail - processed
        turnaround = s["backlog"] / max(weekday_cap_claims, 1.0)
        sla = 97.0 if turnaround <= 2.0 else max(20.0, 97.0 - 7.0 * (turnaround - 2.0))
        util_claims = (arrivals / max(claims_cap, 1.0)) if cap_dow >= 1 else (arrivals / max(weekday_cap_claims * 0.55, 1.0))

        # --- contact centre ---------------------------------------------------------------
        call_season = 1.0
        if d.month in (6, 7, 8):
            call_season = 1.06
        calls_mult = fx.get("calls_mult", 1.0)
        calls = in_force_total * CALLS_PER_POLICY_DAY * DOW_CALLS[dow(d)] * call_season * calls_mult
        calls += max(0.0, s["backlog"] - 3500) * 0.035
        calls *= float(rng.normal(1.0, 0.04))
        care_cap = eff_staff["care"] * DEPT_COSTS["care"].productivity * prod["care"] * CARE_CAPACITY_DOW[dow(d)]
        util_care = calls / max(care_cap, 1.0)
        wait = min(45 + 900 * max(0.0, util_care - 0.9) ** 1.3, 1200.0)
        answered = min(calls, care_cap * 1.02)
        abandon = float(min(max((wait - 90) / 900, 0.0), 0.35))
        csat = 83 - 0.02 * max(0.0, wait - 90) - 1.2 * max(0.0, turnaround - 2.0) - 0.25 * s["price_shock"] + float(rng.normal(0, 0.4))
        csat = float(min(max(csat, 40), 95))
        nps_target = 27 + 0.4 * (csat - 80) - 0.9 * s["price_shock"] + lv.nps_delta + fx.get("nps", 0.0)
        s["nps"] = float(min(max(s["nps"] + 0.04 * (nps_target - s["nps"]) + float(rng.normal(0, 0.15)), -20), 60))
        s["csat"] = csat
        s["price_shock"] *= 0.985

        # --- cancellations ----------------------------------------------------------------
        svc = 1 + 0.015 * max(0.0, 92 - sla) + 0.0008 * max(0.0, wait - 150)
        nps_f = 1 + (24 - s["nps"]) / 250
        seas_l = 1.2 if d.month in (4, 5) else (1.1 if d.month in (6, 7) else 1.0)
        price_f = 1 + 0.035 * s["price_shock"]
        cancel_rows, cancels_total, reasons_acc = [], 0, np.zeros(len(CANCEL_REASONS))
        for pid, p in self.products.items():
            lam = s["in_force"][pid] * p.lapse / 365 * svc * nps_f * seas_l * price_f * fx.get("lapse_mult", 1.0) * lv.lapse_mult
            c = int(rng.poisson(max(lam, 0)))
            c = min(c, int(s["in_force"][pid]))
            if c > 0:
                pr = np.array([0.26 * price_f, 0.10 * svc, 0.38, 0.18, 0.08 if p.category in ("ovhc", "oshc") else 0.02])
                pr = pr / pr.sum()
                for reason, k in zip(CANCEL_REASONS, rng.multinomial(c, pr)):
                    if k > 0:
                        cancel_rows.append((d.isoformat(), pid, reason, int(k)))
            s["in_force"][pid] += prod_sales[pid] - c
            cancels_total += c
        share = np.array(list(s["in_force_state"].values()))
        if cancels_total > 0 and share.sum() > 0:
            for st, k in zip(STATES, rng.multinomial(cancels_total, share / share.sum())):
                s["in_force_state"][st] = max(s["in_force_state"][st] - int(k), 0)

        # --- marketing, brand ----------------------------------------------------------------
        mkt_spend = BASE_MARKETING_DAILY * (1.15 if d.month in (3, 6) else 1.0)
        s["brand"] = float(min(max(s["brand"] + lv.brand_gain + fx.get("brand", 0.0) / 6 - 0.012 * (s["brand"] - 42) / 10 + float(rng.normal(0, 0.03)), 15), 90))
        lead_rows = [(d.isoformat(), cid, leads[cid], round(mkt_spend * leads[cid] / max(sum(leads.values()), 1), 2), round(conv_by_channel[cid], 4))
                     for cid in CHANNELS]

        # --- people ---------------------------------------------------------------------------
        team_rows, exits_total = [], 0
        util_by = {"claims": util_claims, "care": util_care, "sales": sales_util}
        for dept, t in s["team"].items():
            u = util_by.get(dept, 0.80 + float(rng.normal(0, 0.02)))
            t["util"] = float(u)
            vac = sum(x[0] for x in t["pipeline"])
            vac_rate = vac / max(t["staff"], 1)
            target = 71 + lv.engagement_bonus.get(dept, 0.0) - 22 * max(0.0, u - 0.95) - 40 * vac_rate
            t["engagement"] = float(min(max(t["engagement"] + 0.03 * (target - t["engagement"]) + float(rng.normal(0, 0.12)), 35), 92))
            rate = BASE_ANNUAL_ATTRITION * (1 + 0.04 * (70 - t["engagement"])) * lv.attrition_mult.get(dept, 1.0) * (1 + 0.8 * max(0.0, u - 1.0))
            exits = int(rng.poisson(max(t["staff"] * rate / 365, 0)))
            exits = min(exits, int(t["staff"] * 0.05) + 1)
            if exits:
                t["staff"] -= exits
                # business-as-usual backfill: replacement arrives in 6-10 weeks
                t["pipeline"].append([exits, (d + timedelta(days=int(rng.integers(42, 70)))).isoformat(), "bau"])
                exits_total += exits
            team_rows.append((d.isoformat(), dept, round(t["staff"], 1), int(sum(x[0] for x in t["pipeline"])), 0, exits,
                              round(t["util"], 3), round(t["engagement"], 2), t["prod"]))
        headcount = sum(t["staff"] for t in s["team"].values())
        engagement = sum(t["engagement"] * t["staff"] for t in s["team"].values()) / max(headcount, 1)

        # --- money ----------------------------------------------------------------------------------
        payroll = sum(t["staff"] * DEPT_COSTS[dp].salary / 365 for dp, t in s["team"].items())
        broker_comm = sales_by_channel["broker"] * 2650 * 0.18 * (lv.broker_commission_pct / 100)
        initiative_cost = lv.cost_today + cost_one_off + broker_comm
        promo_loss = s["promo_pool"] / 365
        revenue = prem_total - promo_loss
        opex = payroll + FIXED_OPEX_DAILY + mkt_spend + initiative_cost + revenue * VARIABLE_EXPENSE
        invest = revenue * INVESTMENT_YIELD
        margin = (revenue + invest - benefits_total - opex) / max(revenue, 1)
        net_adds = total_sales - cancels_total
        s["days"] += 1
        s["date"] = d.isoformat()

        kpi = {
            "date": d.isoformat(), "policies_in_force": round(sum(s["in_force"].values()), 1), "new_sales": total_sales, "cancellations": cancels_total,
            "net_adds": net_adds, "leads": sum(leads.values()), "conversion": round(total_sales / max(sum(leads.values()), 1), 4),
            "premium_revenue": round(revenue, 2), "claims_incurred": round(benefits_total, 2), "loss_ratio": round(benefits_total / max(revenue, 1), 4),
            "opex": round(opex, 2), "initiative_cost": round(initiative_cost, 2), "margin": round(margin, 4),
            "claims_arrivals": int(arrivals), "claims_processed": int(processed), "claims_backlog": int(s["backlog"]), "claims_sla_pct": round(sla, 1),
            "calls": int(calls), "calls_answered": int(answered), "avg_wait_s": round(wait, 1), "abandon_pct": round(abandon * 100, 1),
            "csat": round(csat, 1), "nps": round(s["nps"], 1), "brand_awareness": round(s["brand"], 1), "marketing_spend": round(mkt_spend, 2),
            "headcount": round(headcount, 1), "engagement": round(engagement, 1), "utilization_claims": round(util_claims, 3),
            "utilization_care": round(util_care, 3), "exits": exits_total,
        }
        if persist:
            st = self.store
            st.insert_many("daily_leads", lead_rows, 5)
            st.insert_many("daily_sales", sales_rows, 6)
            st.insert_many("daily_sales_age", age_rows, 4)
            st.insert_many("daily_cancellations", cancel_rows, 4)
            st.insert_many("daily_claims", [r[:5] for r in claims_rows], 5)
            st.insert_many("daily_book", book_rows, 4)
            st.insert_many("daily_team", team_rows, 9)
            st.insert_kpi(kpi)
            for e in started:
                st.db.execute("INSERT INTO events(date,type,name,description,start_date,end_date,effects) VALUES (?,?,?,?,?,?,?)",
                              (d.isoformat(), e["type"], e["name"], e["desc"], e["start"], e["end"], json.dumps(e["fx"])))
        return DayResult(d.isoformat(), kpi, started, notes)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _event(d: date, typ: str, name: str, desc: str, fx: dict[str, float], days: int) -> dict[str, Any]:
        return {"type": typ, "name": name, "desc": desc, "fx": fx, "start": d.isoformat(), "end": (d + timedelta(days=days)).isoformat()}

    @staticmethod
    def _effects(events: list[dict[str, Any]]) -> dict[str, float]:
        out: dict[str, float] = {}
        for e in events:
            for k, v in e["fx"].items():
                if k in ("nps", "brand"):
                    out[k] = out.get(k, 0.0) + v
                else:
                    out[k] = out.get(k, 1.0) * v
        return out

    def _launch(self, ini_id: str, d: date) -> str:
        ini = self.initiatives[ini_id]
        p = ini["params"]
        pid = f"new_{ini_id.lower()}"
        r = ini.get("realised", 1.0)
        prod = Product(pid, p["name"], p["category"], p.get("tier"), p["monthly_price"],
                       {"hospital": 0.86, "extras": 0.80, "combined": 0.86}.get(p["category"], 0.84),
                       {"hospital": 3800, "extras": 150, "combined": 450}.get(p["category"], 600), p["expected_share"] * r, 0.0,
                       [.2, .3, .25, .18, .07], p.get("target", ""), p.get("description", ""), launched=d.isoformat(), lapse=0.15,
                       inclusions=["See product disclosure statement"])
        # take share from similar plans (cannibalisation)
        similar = [x for x in self.products.values() if x.category == prod.category and x.active]
        take = prod.sales_share
        tot = sum(x.sales_share for x in similar) or 1.0
        for x in similar:
            x.sales_share -= take * x.sales_share / tot * 0.6
        self.products[pid] = prod
        self.s["in_force"][pid] = 0.0
        self.s["price_idx"][pid] = 1.0
        customs = self.store.get_kv("custom_products", {})
        customs[pid] = {k: getattr(prod, k) for k in prod.__dataclass_fields__}
        self.store.set_kv("custom_products", customs)
        ini["product_id"] = pid
        return f"Launched new plan '{prod.name}' (${prod.price:.0f}/month)"

    def _update_initiative_status(self, d: date) -> None:
        for ini in self.initiatives.values():
            if ini["status"] == "approved" and ini.get("start_date") and ini["start_date"] <= d.isoformat():
                ini["status"] = "running"
            if ini["status"] == "running" and ini.get("end_date") and ini["end_date"] < d.isoformat():
                ini["status"] = "completed"
            if ini["status"] == "running" and not ini.get("end_date"):
                lead_days = (d - date.fromisoformat(ini["start_date"])).days
                if lead_days > 120:
                    ini["status"] = "completed"
