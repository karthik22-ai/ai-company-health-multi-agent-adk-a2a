"""Strategic initiatives: what agents may propose, how each is costed and estimated, and how it moves the simulation.

An initiative has an *expected* effect (what the proposer is told and writes in the business case) and a *realised* effect:
at approval a hidden luck factor (log-normal around 1.0) is drawn, so some bets under-deliver and some over-deliver – exactly
what the post-implementation reviews are for. Effects always flow through `Levers`, which the daily engine reads.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from hq.company.catalog import AGE_BANDS, CHANNELS, DEPT_COSTS, PRODUCT_BY_ID

STATUSES = ["proposed", "in_review", "approved", "rejected", "running", "completed", "cancelled"]

LEAD_DAYS = {"marketing_campaign": 3, "promo_discount": 2, "new_product": 35, "hire": 0, "training": 7, "wellbeing_program": 7,
             "automation": 45, "provider_deal": 30, "retention_program": 5, "preventive_program": 14, "broker_commission": 7}

KIND_HELP: dict[str, dict[str, Any]] = {
    "marketing_campaign": {"summary": "Extra media spend in one channel for a period.",
                           "params": {"channel": f"one of {[c for c in CHANNELS if c != 'corporate']}", "daily_budget": "AUD per day, 5000-120000", "days": "7-60"}},
    "promo_discount": {"summary": "Discount for NEW joiners on one plan (never for existing members).",
                       "params": {"product_id": "plan id from get_products", "discount_pct": "5-20", "days": "14-60"}},
    "new_product": {"summary": "Launch a new plan (30-60 days to build).",
                    "params": {"name": "plan name", "category": "hospital|extras|combined|ambulance|ovhc|oshc", "tier": "gold|silver|bronze|basic or empty",
                               "monthly_price": "AUD single, 20-500", "expected_share": "share of new sales, 0.01-0.10", "target": "who it is for",
                               "description": "one sentence"}},
    "hire": {"summary": "Recruit staff into a department (arrive in ~5-8 weeks, ~2 months to full productivity).",
             "params": {"dept": "department id", "count": "1-40"}},
    "training": {"summary": "Upskill a department (lifts productivity and engagement for ~4 months).",
                 "params": {"dept": "department id", "budget": "total AUD, 20000-600000"}},
    "wellbeing_program": {"summary": "Wellbeing/recognition program (lifts engagement, lowers attrition).",
                          "params": {"dept": "department id or 'all'", "budget": "total AUD, 20000-800000"}},
    "automation": {"summary": "Automate a process (45-90 day rollout with some disruption, then permanent productivity gain).",
                   "params": {"process": "claims|care|sales", "gain_pct": "expected productivity gain, 5-35", "cost": "AUD, 200000-6000000"}},
    "provider_deal": {"summary": "Negotiate provider/network agreements to cut benefit cost per claim.",
                      "params": {"focus": "hospital|extras|dental|optical|physio", "expected_saving_pct": "1-6", "cost": "AUD, 50000-1500000"}},
    "retention_program": {"summary": "Targeted retention offers/calls to reduce cancellations.",
                          "params": {"segment": f"'all' or one of {AGE_BANDS}", "daily_budget": "AUD per day, 3000-60000", "days": "14-90"}},
    "preventive_program": {"summary": "Preventive health program that lowers hospital claims over time (slow payback).",
                           "params": {"focus": "cardiac|diabetes|mental_health|musculoskeletal", "daily_budget": "AUD per day, 5000-60000", "days": "60-180"}},
    "broker_commission": {"summary": "Change broker commission (more commission, more broker leads, higher cost).",
                          "params": {"change_pct": "-20 to +20"}},
}

CATEGORIES = {"hospital", "extras", "combined", "ambulance", "ovhc", "oshc"}


@dataclass
class Levers:
    """Everything initiatives (and hiring/training) change in the engine today."""
    extra_leads: dict[str, float] = field(default_factory=dict)          # channel -> extra leads/day
    leads_mult: dict[str, float] = field(default_factory=dict)           # channel -> multiplier
    conv_mult: float = 1.0
    product_weight: dict[str, float] = field(default_factory=dict)       # product -> new-sales weight multiplier
    promo_discount: dict[str, float] = field(default_factory=dict)       # product -> discount fraction on new joiners
    lapse_mult: float = 1.0
    claims_mult: dict[str, float] = field(default_factory=dict)          # category/focus -> multiplier on benefits
    prod_mult: dict[str, float] = field(default_factory=dict)            # dept -> productivity multiplier
    engagement_bonus: dict[str, float] = field(default_factory=dict)     # dept -> target engagement points
    attrition_mult: dict[str, float] = field(default_factory=dict)       # dept -> multiplier
    cost_today: float = 0.0
    brand_gain: float = 0.0
    nps_delta: float = 0.0
    broker_commission_pct: float = 0.0

    def mul(self, d: dict[str, float], key: str, v: float) -> None:
        d[key] = d.get(key, 1.0) * v

    def add(self, d: dict[str, float], key: str, v: float) -> None:
        d[key] = d.get(key, 0.0) + v


def _num(params: dict[str, Any], key: str, lo: float, hi: float, errors: list[str], default: float | None = None) -> float:
    v = params.get(key, default)
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        errors.append(f"{key} must be a number")
        return lo
    if not lo <= x <= hi:
        errors.append(f"{key} must be between {lo:g} and {hi:g} (got {x:g})")
    return min(max(x, lo), hi)


def validate_params(kind: str, params: dict[str, Any], product_ids: set[str]) -> tuple[dict[str, Any], list[str]]:
    """Return (clean params, errors). Errors are readable by the LLM so it can fix its proposal."""
    e: list[str] = []
    p: dict[str, Any] = {}
    if kind not in KIND_HELP:
        return {}, [f"unknown kind '{kind}'. Choose from {sorted(KIND_HELP)}"]
    if kind == "marketing_campaign":
        ch = params.get("channel")
        if ch not in CHANNELS or ch == "corporate":
            e.append(f"channel must be one of {[c for c in CHANNELS if c != 'corporate']}")
        p = {"channel": ch, "daily_budget": _num(params, "daily_budget", 5_000, 120_000, e), "days": int(_num(params, "days", 7, 60, e))}
    elif kind == "promo_discount":
        if params.get("product_id") not in product_ids:
            e.append(f"product_id must be one of {sorted(product_ids)}")
        p = {"product_id": params.get("product_id"), "discount_pct": _num(params, "discount_pct", 5, 20, e), "days": int(_num(params, "days", 14, 60, e))}
    elif kind == "new_product":
        cat = params.get("category")
        if cat not in CATEGORIES:
            e.append(f"category must be one of {sorted(CATEGORIES)}")
        tier = params.get("tier") or None
        if cat in ("hospital", "combined") and tier not in ("gold", "silver", "bronze", "basic"):
            e.append("hospital and combined plans must use a tier: gold, silver, bronze or basic (government product tiers)")
        if not params.get("name"):
            e.append("name is required")
        p = {"name": str(params.get("name", ""))[:60], "category": cat, "tier": tier, "monthly_price": _num(params, "monthly_price", 20, 500, e),
             "expected_share": _num(params, "expected_share", 0.01, 0.10, e, 0.03), "target": str(params.get("target", ""))[:80],
             "description": str(params.get("description", ""))[:200]}
    elif kind == "hire":
        d = params.get("dept")
        if d not in DEPT_COSTS:
            e.append(f"dept must be one of {sorted(DEPT_COSTS)}")
        p = {"dept": d, "count": int(_num(params, "count", 1, 40, e))}
    elif kind in ("training", "wellbeing_program"):
        d = params.get("dept")
        if d not in DEPT_COSTS and not (kind == "wellbeing_program" and d == "all"):
            e.append(f"dept must be one of {sorted(DEPT_COSTS)}" + (" or 'all'" if kind == "wellbeing_program" else ""))
        p = {"dept": d, "budget": _num(params, "budget", 20_000, 800_000, e)}
    elif kind == "automation":
        if params.get("process") not in ("claims", "care", "sales"):
            e.append("process must be claims, care or sales")
        p = {"process": params.get("process"), "gain_pct": _num(params, "gain_pct", 5, 35, e), "cost": _num(params, "cost", 200_000, 6_000_000, e)}
    elif kind == "provider_deal":
        if params.get("focus") not in ("hospital", "extras", "dental", "optical", "physio"):
            e.append("focus must be hospital, extras, dental, optical or physio")
        p = {"focus": params.get("focus"), "expected_saving_pct": _num(params, "expected_saving_pct", 1, 6, e), "cost": _num(params, "cost", 50_000, 1_500_000, e)}
    elif kind == "retention_program":
        seg = params.get("segment", "all")
        if seg != "all" and seg not in AGE_BANDS:
            e.append(f"segment must be 'all' or one of {AGE_BANDS}")
        p = {"segment": seg, "daily_budget": _num(params, "daily_budget", 3_000, 60_000, e), "days": int(_num(params, "days", 14, 90, e))}
    elif kind == "preventive_program":
        if params.get("focus") not in ("cardiac", "diabetes", "mental_health", "musculoskeletal"):
            e.append("focus must be cardiac, diabetes, mental_health or musculoskeletal")
        p = {"focus": params.get("focus"), "daily_budget": _num(params, "daily_budget", 5_000, 60_000, e), "days": int(_num(params, "days", 60, 180, e))}
    elif kind == "broker_commission":
        p = {"change_pct": _num(params, "change_pct", -20, 20, e)}
    return p, e


def duration_days(kind: str, p: dict[str, Any]) -> int:
    """How long the initiative's *active period* lasts after it starts (0 = permanent effect)."""
    if kind in ("marketing_campaign", "promo_discount", "retention_program", "preventive_program"):
        return int(p["days"])
    if kind == "training":
        return 120
    if kind == "wellbeing_program":
        return 180
    if kind == "broker_commission":
        return 180
    return 0


def estimate(kind: str, p: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Expected cost and effect shown to proposers/reviewers. `ctx` carries today's baselines from the engine."""
    sales_pd = ctx.get("sales_per_day", {})
    hc = ctx.get("headcount", {})
    out: dict[str, Any] = {"cost": 0.0, "run_rate_annual": 0.0, "headline": "", "metric": "", "delta": 0.0, "horizon_days": 30}
    if kind == "marketing_campaign":
        ch = CHANNELS[p["channel"]]
        extra = (p["daily_budget"] / ch.cpl) / (1 + p["daily_budget"] / (ch.cpl * ch.base_leads))
        sales = extra * ch.conv * p["days"]
        out.update(cost=p["daily_budget"] * p["days"], metric="new_sales", delta=sales, horizon_days=p["days"],
                   headline=f"~{extra:,.0f} extra leads/day → ~{sales:,.0f} extra policies over {p['days']} days")
    elif kind == "promo_discount":
        prod = PRODUCT_BY_ID[p["product_id"]]
        d = p["discount_pct"] / 100
        base = sales_pd.get(p["product_id"], 30)
        extra = base * 3.0 * d * p["days"]
        foregone = (base * (1 + 3.0 * d)) * p["days"] * prod.price * 12 * d
        out.update(cost=foregone, metric="new_sales", delta=extra, horizon_days=p["days"],
                   headline=f"~{extra:,.0f} extra {prod.name} policies; foregone premium ~${foregone:,.0f} over 12 months")
    elif kind == "new_product":
        total = sum(sales_pd.values()) or 600
        sales = total * p["expected_share"] * 90
        out.update(cost=400_000 + 60 * p["monthly_price"] * 100, metric="new_sales", delta=sales, horizon_days=90,
                   headline=f"~{p['expected_share']*100:.1f}% of new sales ≈ {sales:,.0f} policies in the first 90 days (partly cannibalising similar plans)")
    elif kind == "hire":
        d = DEPT_COSTS[p["dept"]]
        out.update(cost=d.salary * 0.12 * p["count"], run_rate_annual=d.salary * p["count"], metric="capacity", delta=p["count"] / max(hc.get(p["dept"], d.headcount), 1) * 100,
                   horizon_days=90, headline=f"+{p['count']} FTE (+{p['count']/max(hc.get(p['dept'], d.headcount),1)*100:.1f}% capacity) at ~${d.salary*p['count']:,.0f}/yr plus ${d.salary*0.12*p['count']:,.0f} recruitment")
    elif kind == "training":
        out.update(cost=p["budget"], metric="productivity", delta=3.0, horizon_days=120, headline="+2–6% productivity and +1–3 engagement points for ~4 months")
    elif kind == "wellbeing_program":
        out.update(cost=p["budget"], metric="engagement", delta=4.0, horizon_days=180, headline="+3–6 engagement points and ~10–18% lower attrition for ~6 months")
    elif kind == "automation":
        out.update(cost=p["cost"], metric="productivity", delta=p["gain_pct"], horizon_days=120,
                   headline=f"+{p['gain_pct']:.0f}% {p['process']} productivity after a 45–90 day rollout (−3% disruption meanwhile)")
    elif kind == "provider_deal":
        out.update(cost=p["cost"], metric="loss_ratio", delta=-p["expected_saving_pct"] / 100 * 0.45, horizon_days=60,
                   headline=f"−{p['expected_saving_pct']:.1f}% benefit cost on {p['focus']} claims from day ~30; slight network-choice trade-off")
    elif kind == "retention_program":
        out.update(cost=p["daily_budget"] * p["days"], metric="cancellations", delta=-8.0, horizon_days=p["days"],
                   headline=f"−5–15% cancellations in the target segment for {p['days']} days")
    elif kind == "preventive_program":
        out.update(cost=p["daily_budget"] * p["days"], metric="loss_ratio", delta=-0.006, horizon_days=p["days"] + 90,
                   headline="−0.5 to −2% hospital benefits after a ~90-day ramp (slow payback)")
    elif kind == "broker_commission":
        out.update(cost=0.0, metric="new_sales", delta=p["change_pct"] * 0.45, horizon_days=60,
                   headline=f"{p['change_pct']:+.0f}% commission → ~{p['change_pct']*0.45:+.0f}% broker leads; commission cost scales with broker sales")
    return out


def realise(kind: str, rng: Any) -> float:
    """Hidden luck factor for how well an initiative actually works (median 1.0)."""
    sigma = {"preventive_program": 0.5, "new_product": 0.45, "automation": 0.35}.get(kind, 0.28)
    return float(min(max(math.exp(rng.normal(0, sigma)), 0.25), 2.2))


def levers_for(ini: dict[str, Any], today: date, lv: Levers, ctx: dict[str, Any]) -> None:
    """Add this initiative's effect for `today` into `lv`. `ini` holds kind, params, start_date, end_date, realised."""
    start = date.fromisoformat(ini["start_date"])
    if today < start:
        return
    kind, p, r = ini["kind"], ini["params"], ini.get("realised", 1.0)
    days_in = (today - start).days
    end = date.fromisoformat(ini["end_date"]) if ini.get("end_date") else None
    active = end is None or today <= end
    if kind == "marketing_campaign" and active:
        ch = CHANNELS[p["channel"]]
        extra = (p["daily_budget"] / ch.cpl) / (1 + p["daily_budget"] / (ch.cpl * ch.base_leads)) * r
        ramp = min(1.0, (days_in + 1) / 4)
        lv.add(lv.extra_leads, p["channel"], extra * ramp)
        lv.cost_today += p["daily_budget"]
        lv.brand_gain += 0.0035 * p["daily_budget"] / 1000 * r
    elif kind == "promo_discount" and active:
        d = p["discount_pct"] / 100
        lv.mul(lv.product_weight, p["product_id"], 1 + 3.0 * d * r)
        lv.conv_mult *= 1 + 0.35 * d * r
        lv.promo_discount[p["product_id"]] = max(lv.promo_discount.get(p["product_id"], 0.0), d)
    elif kind == "new_product":
        pass                                                    # handled by the engine at launch
    elif kind == "training":
        per_head = p["budget"] / max(ctx["headcount"].get(p["dept"], 1), 1)
        f = 0.06 * (1 - math.exp(-per_head / 600)) * r
        if days_in < 14:
            lv.cost_today += p["budget"] / 14
        if days_in >= 14 and active:
            lv.mul(lv.prod_mult, p["dept"], 1 + f)
            lv.add(lv.engagement_bonus, p["dept"], 2.5 * f / 0.06)
    elif kind == "wellbeing_program":
        depts = list(DEPT_COSTS) if p["dept"] == "all" else [p["dept"]]
        total_hc = sum(ctx["headcount"].get(d, 1) for d in depts)
        per_head = p["budget"] / max(total_hc, 1)
        f = (1 - math.exp(-per_head / 350)) * r
        if days_in < 30:
            lv.cost_today += p["budget"] / 30
        if active:
            for d in depts:
                lv.add(lv.engagement_bonus, d, 6.0 * f)
                lv.mul(lv.attrition_mult, d, 1 - 0.20 * f)
    elif kind == "automation":
        proc = {"claims": "claims", "care": "care", "sales": "sales"}[p["process"]]
        rollout = 60
        if days_in < rollout:
            lv.mul(lv.prod_mult, proc, 0.97)
            lv.cost_today += p["cost"] / rollout
        else:
            lv.mul(lv.prod_mult, proc, 1 + p["gain_pct"] / 100 * r)
    elif kind == "provider_deal":
        if days_in < 30:
            lv.cost_today += p["cost"] / 30
        else:
            lv.mul(lv.claims_mult, p["focus"], 1 - p["expected_saving_pct"] / 100 * r)
            lv.nps_delta -= 0.4
    elif kind == "retention_program" and active:
        cover = 1.0 if p["segment"] == "all" else 0.25
        eff = min(0.18, 0.05 + 0.025 * math.log1p(p["daily_budget"] / 20_000) * 4) * r * cover
        lv.lapse_mult *= 1 - eff
        lv.cost_today += p["daily_budget"]
    elif kind == "preventive_program":
        ramp = min(1.0, days_in / 90)
        fade = 1.0 if active else max(0.0, 1 - ((today - end).days) / 180)  # type: ignore[operator]
        eff = (0.008 + 0.012 * min(1.0, p["daily_budget"] / 40_000)) * r * ramp * fade
        lv.mul(lv.claims_mult, "hospital", 1 - eff)
        if active:
            lv.cost_today += p["daily_budget"]
    elif kind == "broker_commission" and active:
        lv.broker_commission_pct += p["change_pct"]
        lv.mul(lv.leads_mult, "broker", 1 + 0.045 * p["change_pct"] / 1.0 * r / 1.0 * 0.1)
