"""Compliance rules every initiative is checked against (synthetic, but modelled on the real Australian framework).

Real-world anchors: the Private Health Insurance Act 2007 (community rating – premiums, eligibility and benefits cannot depend on health
status, claims history or age beyond Lifetime Health Cover; hospital product tiers; annual premium round effective 1 April approved by
the Minister), ASIC rules on misleading conduct, the Privacy Act 1988 (health information is sensitive information), the Private Health
Insurance Ombudsman, and APRA prudential standards. These are checks for the simulation, not legal advice.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

SENSITIVE = re.compile(r"health status|medical history|claims? history|diagnos|pre-?existing condition|risk score|chronic|"
                       r"high[- ]?risk members|sick|low[- ]?risk members|cherry[- ]?pick", re.I)
MISLEADING = re.compile(r"guarantee|no waiting periods?|100% cover|everything covered|never pay|free forever", re.I)
MINORS = re.compile(r"children under|under[- ]?18|minors|teen(?:ager)?s? (?:direct|marketing)", re.I)


@dataclass
class RuleResult:
    ok: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.ok = False
        self.violations.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "violations": self.violations, "warnings": self.warnings}


def check_initiative(kind: str, params: dict[str, Any], text: str, cost: float, ctx: dict[str, Any]) -> RuleResult:
    """ctx: {budget_remaining, headcount:{dept:n}}"""
    r = RuleResult()
    blob = f"{text} {json.dumps(params)}"
    if SENSITIVE.search(blob) and kind != "preventive_program":
        r.fail("Community rating / privacy: offers, prices, eligibility or targeting cannot be based on health status or claims history "
               "(Private Health Insurance Act) and health information is sensitive information under the Privacy Act (APP 3, 6, 7).")
    elif SENSITIVE.search(blob):
        r.warnings.append("Preventive programs may use health information only with the member's consent (Privacy Act, APP 3/6); invitations must not affect premiums.")
    if MISLEADING.search(blob):
        r.fail("Misleading or deceptive conduct (ASIC Act): claims like 'guarantee' / 'no waiting periods' / '100% cover' cannot be used.")
    if MINORS.search(blob) and kind in ("marketing_campaign", "promo_discount"):
        r.fail("Marketing directed at under-18s is not permitted.")
    if kind == "promo_discount":
        if params["discount_pct"] > 15 and params["days"] > 45:
            r.warnings.append("Deep, long discounts attract ACCC/ASIC scrutiny; consider a shorter or shallower offer.")
        r.warnings.append("Discounts apply to new joiners only; existing members' premiums can change only in the annual premium round (1 April).")
    if kind == "new_product":
        if params.get("category") in ("hospital", "combined") and not params.get("tier"):
            r.fail("Hospital and combined plans must be classified as Gold, Silver, Bronze or Basic (government product tiers).")
        floor = {"gold": 200, "silver": 140, "bronze": 100, "basic": 70}.get(params.get("tier") or "", 0)
        if params.get("category") in ("hospital", "combined") and params["monthly_price"] < floor:
            r.warnings.append(f"A {params.get('tier')} plan priced below ${floor}/month would likely lose money (benefits are regulated minimums).")
    if kind == "broker_commission":
        if params["change_pct"] > 15:
            r.fail("Commission increases above 15% risk conflicted-remuneration findings (ASIC / Ombudsman).")
        elif params["change_pct"] > 10:
            r.warnings.append("Commission increases above 10% will draw regulator attention to broker incentives.")
    if kind == "hire":
        hc = max(ctx.get("headcount", {}).get(params["dept"], 10), 1)
        if params["count"] > 0.30 * hc and params["count"] > 5:
            r.fail(f"Hiring {params['count']} into a team of {hc:.0f} (+{params['count']/hc*100:.0f}%) cannot be onboarded safely in one quarter; stage it.")
        elif params["count"] > 0.12 * hc and params["count"] > 3:
            r.warnings.append("Large single hiring waves slow ramp-up; consider staging it.")
    if kind == "automation":
        r.warnings.append("Rollout disrupts the process for ~2 months; communicate with members and monitor claims accuracy (misdirected payments risk).")
    if kind == "provider_deal":
        r.warnings.append("Network changes need member notification and must not reduce minimum benefits (Ombudsman complaints risk).")
    budget = ctx.get("budget_remaining")
    if budget is not None:
        if cost > budget:
            r.fail(f"Cost ${cost:,.0f} exceeds the remaining strategy budget ${budget:,.0f}.")
        elif cost > 0.2 * budget:
            r.warnings.append(f"Uses {cost/budget*100:.0f}% of the remaining strategy budget; needs the CEO and CFO to agree on priority.")
    return r


def premium_round_window(effective: date, today: date) -> bool:
    """Premium changes for existing members are only allowed with an effective date of 1 April, decided in the weeks before."""
    return effective.month == 4 and effective.day == 1 and 0 <= (effective - today).days <= 45


def check_premium_round(changes: dict[str, float], weights: dict[str, float], cap: float, effective: date, today: date) -> RuleResult:
    r = RuleResult()
    if not premium_round_window(effective, today):
        r.fail("Premium changes for existing members can only take effect on 1 April and must be decided within 45 days before it.")
    total = sum(weights.get(p, 0) for p in changes) or 1.0
    avg = sum(changes[p] * weights.get(p, 0) for p in changes) / total
    full_avg = sum(changes.get(p, 0.0) * w for p, w in weights.items()) / (sum(weights.values()) or 1.0)
    if full_avg > cap + 1e-9:
        r.fail(f"Weighted average increase {full_avg*100:.2f}% exceeds the approved industry cap of {cap*100:.2f}%.")
    for p, c in changes.items():
        if c > cap + 0.02:
            r.fail(f"{p}: +{c*100:.1f}% is more than 2 points above the cap ({cap*100:.2f}%); the Department of Health would likely reject it.")
        if c < -0.05:
            r.warnings.append(f"{p}: a cut of {c*100:.1f}% would need cross-subsidy justification; check community-rating and solvency (APRA).")
    if avg < 0:
        r.warnings.append("A net premium cut puts the loss ratio and solvency targets at risk.")
    return r
