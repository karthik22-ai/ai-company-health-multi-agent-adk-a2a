"""Offline stand-in for the agents' strategic reasoning (used by MockLlm when no Gemini is configured).

Each mode reads the real business tools (through the function responses ADK feeds back) and chooses its next tool call with simple,
transparent rules. With real Gemini none of this is used: the agents reason for themselves using the same tools.
"""
from __future__ import annotations

import json
from typing import Any

from google.genai import types

KIND_FOR_ALERT = {"claims_sla": ("hire", "claims"), "capacity_claims": ("hire", "claims"), "call_wait": ("hire", "care"), "capacity_care": ("hire", "care")}


def _fc(name: str, **args: Any) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=name, args=args))


def _text(t: str) -> list[types.Part]:
    return [types.Part(text=t)]


class Replies:
    """Access to earlier tool responses by tool name."""

    def __init__(self, calls: list[str], responses: list[Any]):
        self.calls, self.responses = calls, responses

    def get(self, name: str, nth: int = 0) -> Any:
        idx = [i for i, c in enumerate(self.calls) if c == name]
        if nth >= len(idx) or idx[nth] >= len(self.responses):
            return None
        r = self.responses[idx[nth]].response
        return r.get("result", r) if isinstance(r, dict) and set(r) == {"result"} else r


def _pct(x: float) -> str:
    return f"{x*100:.1f}%"


def next_action(mode: str, agent_id: str, calls: list[str], responses: list[Any], mock: dict[str, Any]) -> list[types.Part]:
    fn = {"brief": _brief, "investigate": _investigate, "propose": _propose, "review": _review, "decide": _decide, "evaluate": _evaluate,
          "standup": _standup, "plan_note": _plan_note, "premium_analyse": _premium_analyse, "premium_propose": _premium_propose,
          "premium_decide": _premium_decide, "board_note": _board_note, "presentation": _presentation, "minutes": _minutes,
          "dashboard": _dashboard, "report": _report, "app": _app, "it_backlog": _it_backlog, "access_review": _access_review, "hire": _hire,
          "resident": _resident, "town_campaign": _town_campaign, "council": _council, "weekly_goals": _weekly_goals}.get(mode)
    if not fn:
        return _text("Done.")
    return fn(agent_id, Replies(calls, responses), len(calls), mock)


# ----------------------------------------------------------------------------- daily
def _brief(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_kpis", window_days=7)]
    if n == 1:
        return [_fc("get_alerts")]
    if n == 2:
        return [_fc("get_forecast", metric="new_sales", days=7)]
    k, alerts, fc = r.get("get_kpis") or {}, r.get("get_alerts") or [], r.get("get_forecast") or {}
    c, ch = k.get("current", {}), k.get("change_pct", {})
    top = [a for a in alerts if a.get("severity") != "info"][:3]
    events = [a["message"] for a in alerts if a.get("severity") == "info"][:2]
    title = f"Daily brief: {c.get('new_sales_per_day', 0):.0f} sales/day, loss ratio {_pct(c.get('loss_ratio', 0))}, SLA {c.get('claims_sla_pct', 0):.0f}%"
    body = (f"Policies {c.get('policies_in_force', 0):,.0f} (net {c.get('net_adds', 0):+.0f}/day). Sales {c.get('new_sales_per_day', 0):.0f}/day "
            f"({ch.get('new_sales_per_day')}% vs prior week); cancellations {c.get('cancellations_per_day', 0):.0f}/day. Loss ratio {_pct(c.get('loss_ratio', 0))}, "
            f"margin {_pct(c.get('margin', 0))}. Claims within SLA {c.get('claims_sla_pct', 0):.1f}%, backlog {c.get('claims_backlog', 0):,.0f}. "
            f"Wait {c.get('avg_wait_s', 0):.0f}s, NPS {c.get('nps', 0):.0f}. Next-7-day sales forecast {fc.get('total', '?')}. "
            + ("Watch: " + "; ".join(a["message"] for a in top) if top else "No alerts.") + (" Context: " + "; ".join(events) if events else ""))
    if n == 3:
        return [_fc("write_note", kind="daily_brief", title=title, body=body)]
    return _text("Daily brief posted. " + (f"{len(top)} item(s) need attention." if top else "All metrics are within thresholds."))


def _investigate(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    alert = mock.get("alert", {})
    key = alert.get("key", "")
    if n == 0:
        return [_fc("get_kpis", window_days=7)]
    if n == 1:
        if key in ("claims_sla", "loss_ratio"):
            return [_fc("get_breakdown", metric="claims", by="claim_type", days=14)]
        if key == "sales_drop" or key == "net_adds":
            return [_fc("get_breakdown", metric="sales", by="channel", days=14)]
        if key.startswith(("capacity_", "attrition_", "engagement")):
            return [_fc("get_team_status", dept=alert.get("dept", ""))]
        return [_fc("get_breakdown", metric="cancellations", by="reason", days=14)]
    data = r.get("get_breakdown") or r.get("get_team_status") or []
    k = (r.get("get_kpis") or {}).get("current", {})
    if isinstance(data, list) and data and "share_pct" in data[0]:
        top = data[0]
        finding = f"Largest contributor: {list(top.values())[0]} ({top['share_pct']}% of {'claims' if 'benefits_aud' in top else 'volume'})."
    elif isinstance(data, dict) and data:
        finding = f"{data.get('dept', alert.get('dept'))}: utilisation {data.get('utilization', 0)*100:.0f}%, engagement {data.get('engagement')}, open roles {data.get('open_roles')}."
    else:
        finding = "No single driver stands out; looks seasonal."
    body = f"Alert: {alert.get('message', '')} Finding: {finding} Claims backlog {k.get('claims_backlog', 0):,.0f}, wait {k.get('avg_wait_s', 0):.0f}s."
    if n == 2:
        return [_fc("write_note", kind="investigation", title=f"Investigation: {key}", body=body)]
    if n == 3 and alert.get("severity") == "high" and key in KIND_FOR_ALERT and mock.get("allow_proposal", True):
        kind, dept = KIND_FOR_ALERT[key]
        team = r.get("get_team_status")
        cnt = 8
        return [_fc("propose_initiative", kind="hire", title=f"Urgent: add {cnt} {dept} staff",
                    rationale=f"{alert.get('message', '')} Utilisation is above capacity; adding {cnt} FTE restores service levels before the backlog drives cancellations.",
                    params_json=json.dumps({"dept": dept, "count": cnt}))]
    return _text(f"Investigated {key}: {finding}")


def _standup(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_alerts")]
    if n == 1:
        return [_fc("list_initiatives", status="approved")]
    alerts = [a for a in (r.get("get_alerts") or []) if a.get("severity") != "info"]
    approved = r.get("list_initiatives") or []
    body = ("Priorities today: " + ("; ".join(a["message"] for a in alerts[:3]) if alerts else "none flagged") + ". "
            + (f"Approved and queued: {', '.join(i['title'] for i in approved[:3])}." if approved else "No new approvals waiting."))
    if n == 2:
        return [_fc("write_note", kind="standup", title="Daily standup", body=body)]
    return _text("Standup note posted.")


# ----------------------------------------------------------------------------- weekly: proposals
def _existing(inis: list[dict], kind: str, dept: str | None = None, pid: str | None = None) -> bool:
    for i in inis or []:
        if i.get("kind") == kind and i.get("status") in ("proposed", "in_review", "approved", "running"):
            p = i.get("params") or {}
            if dept and p.get("dept") not in (dept, None) and p.get("process") != dept:
                continue
            if pid and p.get("product_id") != pid:
                continue
            return True
    return False


def propose_for(dept: str, k: dict, team: dict, alerts: list, budget: float, inis: list, products: list, week: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    c = k.get("current", {})
    hc = lambda d: team.get(d, {}).get("headcount", 10)  # noqa: E731
    if dept == "claims":
        if (c.get("claims_sla_pct", 100) < 92 or c.get("claims_utilization", 0) > 0.98) and not _existing(inis, "hire", "claims"):
            n = max(4, round(hc("claims") * 0.08))
            out.append({"kind": "hire", "title": f"Add {n} claims assessors", "params": {"dept": "claims", "count": n},
                        "why": f"Claims utilisation is {c.get('claims_utilization', 0)*100:.0f}% and only {c.get('claims_sla_pct', 0):.0f}% are within SLA (target 92%). Backlog {c.get('claims_backlog', 0):,.0f}. {n} FTE restores headroom before winter/peak."})
        if c.get("claims_utilization", 0) > 0.9 and budget > 3_000_000 and not _existing(inis, "automation", "claims"):
            out.append({"kind": "automation", "title": "Auto-adjudicate simple extras claims", "params": {"process": "claims", "gain_pct": 18, "cost": 1_600_000},
                        "why": "Extras claims are ~80% of volume and mostly rule-based; automation lifts assessor productivity ~18% after rollout, a permanent capacity gain without more headcount."})
    elif dept == "care":
        if (c.get("avg_wait_s", 0) > 150 or c.get("care_utilization", 0) > 1.0) and not _existing(inis, "hire", "care"):
            n = max(3, round(hc("care") * 0.08))
            out.append({"kind": "hire", "title": f"Add {n} contact-centre agents", "params": {"dept": "care", "count": n},
                        "why": f"Average wait is {c.get('avg_wait_s', 0):.0f}s (target 150s) with utilisation {c.get('care_utilization', 0)*100:.0f}%; abandonment {c.get('abandon_pct', 0):.1f}%. Long waits raise cancellations."})
        if c.get("nps", 30) < 26 and not _existing(inis, "training", "care"):
            out.append({"kind": "training", "title": "First-contact-resolution training", "params": {"dept": "care", "budget": 120_000},
                        "why": f"NPS is {c.get('nps', 0):.0f} (target 28). Better first-call resolution reduces repeat calls and lifts satisfaction."})
    elif dept == "sales":
        if c.get("net_adds", 999) < 120 and not _existing(inis, "marketing_campaign"):
            ch = "comparison_site" if week % 2 else "online_direct"
            out.append({"kind": "marketing_campaign", "title": f"Always-on push in {ch.replace('_', ' ')}", "params": {"channel": ch, "daily_budget": 22_000, "days": 28},
                        "why": f"Net adds are {c.get('net_adds', 0):.0f}/day against a 120 target and conversion is {c.get('conversion', 0)*100:.1f}%. {ch.replace('_', ' ')} is our scalable low-cost lead source; at 22k/day the marginal cost per policy stays well under customer lifetime value."})
    elif dept == "mkt":
        canc = c.get("cancellations_per_day", 0)
        if canc > 200 and not _existing(inis, "retention_program"):
            out.append({"kind": "retention_program", "title": "Save-the-member program", "params": {"segment": "all", "daily_budget": 9_000, "days": 45},
                        "why": f"Cancellations are {canc:.0f}/day; each saved policy is worth ~$1,500 lifetime contribution. Proactive offers and callbacks at 9k/day typically cut cancellations 5-10%."})
        elif not _existing(inis, "marketing_campaign") and c.get("brand_awareness", 50) < 45:
            out.append({"kind": "marketing_campaign", "title": "Brand awareness burst", "params": {"channel": "retail_partner", "daily_budget": 12_000, "days": 21},
                        "why": f"Brand awareness is {c.get('brand_awareness', 0):.0f}; partner placements lift leads and awareness cheaply."})
    elif dept == "prod":
        low = sorted([p for p in products if p.get("active") and p["category"] in ("hospital", "combined") and p.get("in_force")],
                     key=lambda p: p["sales_28d"] / max(p["in_force"], 1))[:1]
        if low and not _existing(inis, "promo_discount", pid=low[0]["id"]) and c.get("net_adds", 999) < 120:
            p = low[0]
            out.append({"kind": "promo_discount", "title": f"10% new-joiner offer on {p['name']}", "params": {"product_id": p["id"], "discount_pct": 10, "days": 30},
                        "why": f"{p['name']} has the weakest sales relative to members in force ({p['sales_28d']} in 28 days vs {p['in_force']:,} members). A time-limited offer for NEW joiners only keeps community rating and existing premiums untouched."})
        if not _existing(inis, "new_product") and c.get("net_adds", 999) < 100 and week % 3 == 0:
            out.append({"kind": "new_product", "title": "Flex Silver digital-first hospital plan",
                        "params": {"name": "Flex Silver", "category": "hospital", "tier": "silver", "monthly_price": 179, "expected_share": 0.05, "target": "digital-first 25-44s",
                                   "description": "Silver hospital cover sold and managed entirely online with a higher excess option."},
                        "why": "Silver is our biggest hospital plan but price-sensitive comparison shoppers choose cheaper rivals; a digital-first variant with a higher excess targets them without discounting the base plan."})
    elif dept == "health":
        if c.get("loss_ratio", 0) > 0.87 and not _existing(inis, "provider_deal"):
            out.append({"kind": "provider_deal", "title": "Hospital network agreement refresh", "params": {"focus": "hospital", "expected_saving_pct": 3, "cost": 450_000},
                        "why": f"Loss ratio is {c.get('loss_ratio', 0)*100:.1f}% (target 87%). Hospital admissions are ~70% of benefits; a 3% saving through preferred-provider agreements is worth far more than its cost."})
        if c.get("loss_ratio", 0) > 0.86 and not _existing(inis, "preventive_program"):
            out.append({"kind": "preventive_program", "title": "Musculoskeletal prevention and physio program", "params": {"focus": "musculoskeletal", "daily_budget": 14_000, "days": 120},
                        "why": "Joint and back conditions drive a large share of elective hospital claims. Early physio and exercise programs (consent-based, no premium impact) lower admissions over 3-6 months."})
    elif dept == "people":
        weak = sorted(team.items(), key=lambda kv: kv[1].get("engagement", 100))[:1]
        for d, t in weak:
            if (t.get("engagement", 100) < 67 or t.get("attrition_annualised", 0) > 0.2) and not _existing(inis, "wellbeing_program"):
                out.append({"kind": "wellbeing_program", "title": f"Wellbeing and recognition program for {d}", "params": {"dept": d, "budget": 110_000},
                            "why": f"{d} engagement is {t.get('engagement')} and attrition runs at {t.get('attrition_annualised', 0)*100:.0f}% a year; replacing a leaver costs ~12% of salary plus lost productivity."})
        stressed = [d for d, t in team.items() if t.get("utilization", 0) > 1.0 and d in ("claims", "care", "sales")]
        if stressed and not _existing(inis, "training", stressed[0]):
            out.append({"kind": "training", "title": f"Productivity training for {stressed[0]}", "params": {"dept": stressed[0], "budget": 90_000},
                        "why": f"{stressed[0]} runs above capacity (utilisation {team[stressed[0]]['utilization']*100:.0f}%); targeted training lifts throughput ~3-5% without new headcount."})
    return out[:2]


def _propose(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    dept = mock.get("dept", agent.split(".")[0])
    steps = [("get_kpis", {"window_days": 28}), ("get_team_status", {"dept": ""}), ("get_alerts", {}), ("get_budget", {}), ("list_initiatives", {"status": ""}), ("get_products", {})]
    if n < len(steps):
        return [_fc(steps[n][0], **steps[n][1])]
    k, team, alerts = r.get("get_kpis") or {}, r.get("get_team_status") or {}, r.get("get_alerts") or []
    budget = (r.get("get_budget") or {}).get("remaining", 0)
    props = propose_for(dept, k, team if isinstance(team, dict) else {}, alerts, budget, r.get("list_initiatives") or [], r.get("get_products") or [], mock.get("week", 0))
    i = n - len(steps)
    if i < len(props):
        p = props[i]
        return [_fc("propose_initiative", kind=p["kind"], title=p["title"], rationale=p["why"], params_json=json.dumps(p["params"]))]
    return _text(f"{len(props)} proposal(s) submitted." if props else "No new initiative needed this week: my metrics are within thresholds or already covered.")


# ----------------------------------------------------------------------------- weekly: review + decide
def _review(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("list_initiatives", status="proposed")]
    if n == 1:
        return [_fc("get_budget")]
    inis = r.get("list_initiatives") or []
    budget = (r.get("get_budget") or {}).get("remaining", 1)
    i = n - 2
    if i < len(inis):
        ini = inis[i]
        comp = ini.get("compliance") or {}
        if agent.startswith("risk."):
            if comp.get("violations"):
                verdict, msg = "object", "Breaches a rule: " + " ".join(comp["violations"])[:200]
            elif comp.get("warnings"):
                verdict, msg = "concerns", "Acceptable with conditions: " + comp["warnings"][0][:180]
            else:
                verdict, msg = "endorse", "No compliance concerns; consistent with community rating and ASIC/Privacy requirements."
        else:
            share = ini.get("cost_est", 0) / max(budget, 1)
            if share > 0.2:
                verdict, msg = "concerns", f"Costs {share*100:.0f}% of the remaining strategy budget; needs a clear payback."
            else:
                verdict, msg = "endorse", f"Cost ${ini.get('cost_est', 0):,.0f} is {share*100:.1f}% of remaining budget; expected effect: {ini.get('headline', '')[:110]}"
        return [_fc("review_initiative", initiative_id=ini["id"], verdict=verdict, comments=msg)]
    return _text(f"Reviewed {len(inis)} proposal(s).")


PRIORITY = {"hire": 3, "automation": 3, "provider_deal": 3, "retention_program": 2, "marketing_campaign": 2, "promo_discount": 2, "new_product": 1,
            "wellbeing_program": 2, "training": 1, "preventive_program": 1, "broker_commission": 0}


def _decide(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    steps = [("list_initiatives", {"status": "in_review"}), ("list_initiatives", {"status": "proposed"}), ("get_alerts", {}), ("get_budget", {})]
    if n < len(steps):
        return [_fc(steps[n][0], **steps[n][1])]
    inis = (r.get("list_initiatives", 0) or []) + (r.get("list_initiatives", 1) or [])
    alerts = [a for a in (r.get("get_alerts") or []) if a.get("severity") != "info"]
    budget = (r.get("get_budget") or {}).get("remaining", 0)
    urgent = {a["dept"] for a in alerts if a["severity"] == "high"}
    max_ok = int(mock.get("max_approvals", 3))

    def score(i: dict) -> float:
        s = PRIORITY.get(i["kind"], 1) + (2 if i["dept"] in urgent else 0)
        return s - i.get("cost_est", 0) / 2_000_000

    plan, spent, ok = [], 0.0, 0
    for i in sorted(inis, key=score, reverse=True):
        objected = any(rv["verdict"] == "object" for rv in i.get("reviews", []))
        comp_ok = (i.get("compliance") or {}).get("ok", True)
        if objected or not comp_ok:
            plan.append((i, "reject", "Rejected on compliance grounds: " + (" ".join((i.get("compliance") or {}).get("violations", []))[:150] or "reviewer objection.")))
        elif ok < max_ok and spent + i.get("cost_est", 0) <= budget * 0.5:
            plan.append((i, "approve", f"Approved: addresses {i['dept']} priority and fits the budget (${i.get('cost_est', 0):,.0f})."))
            spent += i.get("cost_est", 0)
            ok += 1
        else:
            plan.append((i, "reject", "Not this cycle: lower priority than the approved items or the budget is reserved. Resubmit with fresh evidence."))
    i = n - len(steps)
    if i < len(plan):
        ini, dec, note = plan[i]
        return [_fc("decide_initiative", initiative_id=ini["id"], decision=dec, note=note)]
    return _text(f"Decided {len(plan)} initiative(s): {sum(1 for p in plan if p[1] == 'approve')} approved.")


# ----------------------------------------------------------------------------- monthly
def _evaluate(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("list_initiatives", status="running")]
    if n == 1:
        return [_fc("list_initiatives", status="completed")]
    inis = ((r.get("list_initiatives", 0) or []) + (r.get("list_initiatives", 1) or []))[:4]
    i = n - 2
    if i < len(inis):
        return [_fc("evaluate_initiative", initiative_id=inis[i]["id"])]
    if n == 2 + len(inis):
        lines = []
        for j in range(len(inis)):
            ev = r.get("evaluate_initiative", j) or {}
            m = ev.get("metrics") or {}
            first = next(iter(m.items()), None)
            if first:
                lines.append(f"{ev.get('title')}: {first[0]} {first[1].get('change_pct_vs_last_year_pattern')}% vs last-year pattern (expected: {str(ev.get('expected'))[:70]}).")
            else:
                lines.append(f"{ev.get('title', '?')}: {ev.get('message', 'not enough data yet')}")
        return [_fc("write_note", kind="lesson", title="Initiative review", body=" ".join(lines) or "No initiatives to evaluate yet.")]
    return _text("Evaluation note posted.")


def _plan_note(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("list_initiatives", status="approved")]
    if n == 1:
        return [_fc("get_budget")]
    inis = r.get("list_initiatives") or []
    b = r.get("get_budget") or {}
    body = ("Approved this week: " + "; ".join(f"{i['title']} (${i.get('cost_est', 0):,.0f}, owner {i['dept']})" for i in inis[:6]) if inis else "No new initiatives approved.") \
        + f" Strategy budget remaining ${b.get('remaining', 0):,.0f}."
    if n == 2:
        return [_fc("write_note", kind="weekly_plan", title="Weekly plan and decisions", body=body)]
    return _text("Weekly plan communicated.")


def _board_note(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_kpis", window_days=28)]
    if n == 1:
        return [_fc("get_budget")]
    c = (r.get("get_kpis") or {}).get("current", {})
    t = (r.get("get_kpis") or {}).get("targets", {})
    missed = [k for k, v in t.items() if not v.get("ok")]
    body = (f"28 days: loss ratio {_pct(c.get('loss_ratio', 0))}, margin {_pct(c.get('margin', 0))}, net adds {c.get('net_adds', 0):.0f}/day, SLA {c.get('claims_sla_pct', 0):.0f}%, "
            f"NPS {c.get('nps', 0):.0f}, engagement {c.get('engagement', 0):.0f}. Targets missed: {', '.join(missed) if missed else 'none'}. "
            f"Strategy budget left ${(r.get('get_budget') or {}).get('remaining', 0):,.0f}.")
    if n == 2:
        return [_fc("write_note", kind="board_note", title="Monthly board summary", body=body)]
    return _text("Board summary posted.")


# ----------------------------------------------------------------------------- annual premium round
def _round_plan(info: dict, products: list[dict]) -> dict[str, float]:
    cap = info.get("industry_approved_average_cap", 0.037)
    out: dict[str, float] = {}
    for p in products:
        if not p.get("active") or p["id"].startswith("new_"):
            continue
        adj = cap * 0.97
        if p["category"] in ("ovhc", "oshc", "ambulance"):
            adj = cap * 0.85
        elif p["id"] in ("combo_young", "hosp_basic", "hosp_bronze"):
            adj = cap * 0.9            # price-sensitive segments
        elif p["id"] in ("combo_senior", "hosp_gold", "combo_gold"):
            adj = cap * 1.04           # highest claims ratios
        out[p["id"]] = round(adj, 4)
    return out


def _premium_analyse(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_kpis", window_days=28)]
    if n == 1:
        return [_fc("premium_round_info")]
    c = (r.get("get_kpis") or {}).get("current", {})
    info = r.get("premium_round_info") or {}
    body = (f"Loss ratio {_pct(c.get('loss_ratio', 0))} vs 87% target; claims inflation ~4%/yr vs the approved industry average increase of {_pct(info.get('industry_approved_average_cap', 0))}. "
            f"A full-cap increase protects margin but raises cancellations (price elasticity ~1.4). Recommend staying 0.1-0.3 pts under the cap, higher on Gold/Seniors (highest claims ratios), lower on Young Adult/Basic/Bronze.")
    if n == 2:
        return [_fc("write_note", kind="premium_analysis", title="Premium round: actuarial view", body=body)]
    return _text(body)


def _premium_propose(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("premium_round_info")]
    if n == 1:
        return [_fc("get_products")]
    plan = _round_plan(r.get("premium_round_info") or {}, r.get("get_products") or [])
    if n == 2:
        return [_fc("write_note", kind="premium_proposal", title="Premium round proposal", body=json.dumps(plan))]
    return _text("PROPOSAL " + json.dumps(plan))


def _premium_decide(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("premium_round_info")]
    if n == 1:
        return [_fc("get_products")]
    plan = _round_plan(r.get("premium_round_info") or {}, r.get("get_products") or [])
    if n == 2:
        return [_fc("submit_premium_round", changes_json=json.dumps(plan))]
    res = r.get("submit_premium_round") or {}
    return _text("Premium round decided: " + (f"+{res.get('weighted_average_increase', 0)*100:.2f}% average from {res.get('effective')}" if res.get("ok") else str(res)[:200]))


# ----------------------------------------------------------------------------- work products (offline stand-ins)
DEPT_CHART = {
    "sales": ("Sales by channel, last 28 days", "bar", "SELECT channel, SUM(sales) AS sales FROM daily_sales WHERE date >= date((SELECT MAX(date) FROM daily_sales), '-28 day') GROUP BY channel ORDER BY sales DESC", "channel", ["sales"]),
    "claims": ("Claims backlog and SLA, 60 days", "line", "SELECT date, claims_backlog, claims_sla_pct FROM daily_kpi ORDER BY date DESC LIMIT 60", "date", ["claims_backlog"]),
    "care": ("Call wait and abandon rate, 60 days", "line", "SELECT date, avg_wait_s, abandon_pct FROM daily_kpi ORDER BY date DESC LIMIT 60", "date", ["avg_wait_s"]),
    "mkt": ("Leads by channel, last 28 days", "bar", "SELECT channel, SUM(leads) AS leads FROM daily_leads WHERE date >= date((SELECT MAX(date) FROM daily_leads), '-28 day') GROUP BY channel", "channel", ["leads"]),
    "people": ("Engagement by department, latest", "bar", "SELECT dept, ROUND(AVG(engagement),1) AS engagement FROM daily_team WHERE date >= date((SELECT MAX(date) FROM daily_team), '-7 day') GROUP BY dept", "dept", ["engagement"]),
    "prod": ("Members in force by plan", "bar", "SELECT product_id, ROUND(in_force) AS members FROM daily_book WHERE date = (SELECT MAX(date) FROM daily_book) ORDER BY members DESC LIMIT 10", "product_id", ["members"]),
}
COMPANY_CHARTS = [
    {"title": "New sales vs cancellations, 90 days", "type": "line", "sql": "SELECT date, new_sales, cancellations FROM daily_kpi ORDER BY date DESC LIMIT 90", "x": "date", "y": ["new_sales", "cancellations"]},
    {"title": "Net adds per day, 90 days", "type": "line", "sql": "SELECT date, net_adds FROM daily_kpi ORDER BY date DESC LIMIT 90", "x": "date", "y": ["net_adds"]},
    {"title": "Loss ratio, 90 days", "type": "line", "sql": "SELECT date, loss_ratio FROM daily_kpi ORDER BY date DESC LIMIT 90", "x": "date", "y": ["loss_ratio"]},
    {"title": "Claims within SLA (%), 90 days", "type": "line", "sql": "SELECT date, claims_sla_pct FROM daily_kpi ORDER BY date DESC LIMIT 90", "x": "date", "y": ["claims_sla_pct"]},
]


def _chart_for(dept: str) -> dict:
    t = DEPT_CHART.get(dept) or ("Net adds per day, 60 days", "line", "SELECT date, net_adds FROM daily_kpi ORDER BY date DESC LIMIT 60", "date", ["net_adds"])
    return {"title": t[0], "type": t[1], "sql": t[2], "x": t[3], "y": t[4]}


def _kline(k: dict) -> list[str]:
    c, ch = k.get("current", {}), k.get("change_pct", {})
    return [f"Sales {c.get('new_sales_per_day', 0):.0f}/day ({ch.get('new_sales_per_day', 0)}% vs prior week)",
            f"Net adds {c.get('net_adds', 0):+.0f}/day; policies {c.get('policies_in_force', 0):,.0f}",
            f"Loss ratio {_pct(c.get('loss_ratio', 0))}, margin {_pct(c.get('margin', 0))}",
            f"Claims within SLA {c.get('claims_sla_pct', 0):.0f}%, call wait {c.get('avg_wait_s', 0):.0f}s"]


def _presentation(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    dept = agent.split(".")[0]
    if n == 0:
        return [_fc("get_kpis", window_days=7)]
    if n == 1:
        lines = _kline(r.get("get_kpis") or {})
        slides = [{"title": f"{dept.upper()}: where we are", "bullets": lines[:3]},
                  {"title": "Trend", "bullets": [lines[3], "Focus for next week: the biggest gap to target"], "chart": _chart_for(dept)},
                  {"title": "Ask", "bullets": [f"On the agenda '{mock.get('agenda', '')[:60]}': we propose to act on the weakest metric", "Decision needed from the CEO this week"]}]
        return [_fc("create_presentation", title=f"{dept.upper()} update", slides_json=json.dumps(slides), agenda=mock.get("agenda", ""), meeting_id=mock.get("meeting_id", ""))]
    return _text("Deck ready: three slides with this week's numbers and one ask.")


def _minutes(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        md = (f"## Agenda\n{mock.get('agenda', '')}\n\n## What was presented\n{mock.get('digest', '') or '- (no decks)'}\n\n"
              "## Decisions\n- Teams to act on the weakest metric in their area this week\n\n## Actions\n- Each presenter: one improvement by next meeting (owner: presenter)\n")
        return [_fc("create_report", title=f"Minutes: {mock.get('agenda', 'meeting')[:60]}", markdown=md, kind="minutes")]
    return _text("Minutes published.")


def _dashboard(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    topic = mock.get("topic", "company")
    if n == 0:
        return [_fc("get_kpis", window_days=7)]
    if n == 1:
        c = (r.get("get_kpis") or {}).get("current", {})
        kpis = [{"label": "Sales / day", "value": f"{c.get('new_sales_per_day', 0):.0f}"}, {"label": "Net adds / day", "value": f"{c.get('net_adds', 0):+.0f}"},
                {"label": "Loss ratio", "value": _pct(c.get("loss_ratio", 0))}, {"label": "Claims SLA", "value": f"{c.get('claims_sla_pct', 0):.0f}%"}]
        charts = COMPANY_CHARTS if topic in ("company", "bi") else [_chart_for(topic), COMPANY_CHARTS[1]]
        title = "Company performance" if topic in ("company", "bi") else f"{topic.upper()} dashboard"
        return [_fc("create_dashboard", title=title, description=f"Live view for {topic} built on daily company data.", charts_json=json.dumps(charts), kpis_json=json.dumps(kpis))]
    resp = r.get("create_dashboard") or {}
    if n == 2 and isinstance(resp, dict) and resp.get("error") and "denied" in resp["error"].lower():
        return [_fc("request_data_access", dataset="daily_team", reason=f"Needed for the {topic} dashboard")]
    return _text(f"Dashboard published ({resp.get('file_id', '?')}).")


def _report(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_kpis", window_days=7)]
    if n == 1:
        lines = _kline(r.get("get_kpis") or {})
        md = "## Headlines\n" + "\n".join(f"- {x}" for x in lines) + f"\n\n## Request\n{mock.get('request', 'Weekly performance report')}\n"
        return [_fc("create_report", title="Weekly performance report" if mock.get("topic") == "weekly" else "Analysis report", markdown=md,
                    charts_json=json.dumps([COMPANY_CHARTS[0]]))]
    return _text(f"Report published ({(r.get('create_report') or {}).get('file_id', '?')}).")


APP_HTML = """<!doctype html><html><head><meta charset=utf-8><style>body{font-family:system-ui;background:#0b1226;color:#e8ecf6;margin:20px}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #26304a;padding:5px}canvas{background:#121a33;border-radius:10px}</style></head>
<body><h1 id=t></h1><canvas id=c width=800 height=240></canvas><div id=tbl></div><script>
const name=Object.keys(HQ_DATA)[0],d=HQ_DATA[name];document.getElementById('t').textContent=HQ_APP.title+' · '+name;
const num=d.columns.findIndex((c,i)=>i>0&&typeof d.rows[0][i]==='number');const x=document.getElementById('c').getContext('2d');
if(num>0){const v=d.rows.map(r=>r[num]),mx=Math.max(...v)||1;x.fillStyle='#22d3ee';v.forEach((y,i)=>x.fillRect(10+i*(780/v.length),230-y/mx*210,Math.max(2,780/v.length-2),y/mx*210))}
document.getElementById('tbl').innerHTML='<table><tr>'+d.columns.map(c=>'<th>'+c+'</th>').join('')+'</tr>'+d.rows.slice(0,50).map(r=>'<tr>'+r.map(v=>'<td>'+v+'</td>').join('')+'</tr>').join('')+'</table>';
</script></body></html>"""


def _app(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        q = mock.get("queries") or {"kpis": "SELECT date, new_sales, net_adds FROM daily_kpi ORDER BY date DESC LIMIT 60"}
        args = dict(title=mock.get("title", "Reporting app"), description=mock.get("request") or "Internal app on live company data.",
                    html=APP_HTML, data_queries_json=json.dumps(q))
        if mock.get("request_id"):
            args["request_id"] = int(mock["request_id"])
        return [_fc("create_app", **args)]
    return _text(f"App deployed ({(r.get('create_app') or {}).get('file_id', '?')}).")


def _it_backlog(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_app_backlog")]
    if n == 1:
        reqs = [x for x in (r.get("get_app_backlog") or {}).get("open", []) if x.get("status") in ("open", "planned")]
        reqs.sort(key=lambda x: ({"ceo": 0, "signal": 1}.get(x.get("source"), 2), x.get("id", 0)))
        ranking = [{"id": x["id"], "decision": "build" if i == 0 else "later", "note": f"{x.get('source')} request from {x.get('dept')}"}
                   for i, x in enumerate(reqs)]
        if ranking:
            return [_fc("prioritise_app_requests", ranking_json=json.dumps(ranking), summary=f"{ranking[0]['note']} first")]
    return _text("Backlog ranked.")


def _access_review(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("list_access_requests")]
    pend = r.get("list_access_requests") or []
    done = sum(1 for c in r.calls if c == "review_access_request")
    if done < len(pend):
        q = pend[done]
        ok = q.get("sensitivity") != "restricted" or len(q.get("reason", "")) > 20
        return [_fc("review_access_request", request_id=q["id"], decision="approve" if ok else "reject",
                    note="Needed for the requester's role" if ok else "Restricted data: give a specific business reason")]
    return _text(f"Reviewed {len(pend)} request(s).")


FIRST = ["Maya", "Arif", "Lucia", "Tobias", "Ngozi", "Hiro", "Elif", "Mateo", "Priya", "Jonah"]
LAST = ["Brennan", "Rahman", "Ortiz", "Lindqvist", "Adeyemi", "Kobayashi", "Yilmaz", "Silva", "Desai", "Cole"]


def _hire(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    dept = mock.get("dept", "claims")
    if n == 0:
        return [_fc("get_team_status", dept=dept)]
    if n == 1:
        i = sum(ord(ch) for ch in dept + str(mock.get("role", ""))) % len(FIRST)
        args = {"dept": dept, "name": f"{FIRST[i]} {LAST[(i * 3) % len(LAST)]}", "role": mock.get("role", "Operations Specialist"),
                "reason": mock.get("request") or f"Approved hiring initiative for {dept}: capacity gap shown by utilisation and backlog"}
        return [types.Part(function_call=types.FunctionCall(name="hire_agent", args=args))]
    res = r.get("hire_agent") or {}
    return _text(f"Hired {res.get('name', '?')} ({res.get('agent_id', '?')})." if res.get("ok") else f"Could not hire: {res.get('error')}")



# ----------------------------------------------------------------------------- the town (offline stand-ins)
def _resident(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    from hq.town.town import mock_choice
    if n == 0:
        return [_fc("my_profile")]
    if n == 1:
        return [_fc("my_feed")]
    if n == 2:
        return [_fc("compare_insurers")]
    prof, feed, comp = r.get("my_profile") or {}, r.get("my_feed") or {}, r.get("compare_insurers") or []
    asks = sum(ord(c) for c in agent) % 3 == 0
    if n == 3 and asks:
        return [_fc("ask_employee", question="What does your extras cover include for dental and optical, and are there waiting periods?")]
    if "buy_policy" not in r.calls and "keep_current_cover" not in r.calls and "cancel_cover" not in r.calls:
        res = {"needs": prof.get("needs", []), "household_kind": prof.get("household_kind", "single"), "income": prof.get("income", "mid"),
               "age": prof.get("age", 35), "price_sensitivity": prof.get("price_sensitivity", .5), "cover": prof.get("cover_details"),
               "mls_if_no_hospital": prof.get("mls_if_no_hospital", 0)}
        choice, why = mock_choice(None, res, comp if isinstance(comp, list) else [], feed if isinstance(feed, dict) else {})
        if choice in (None, "keep"):
            return [_fc("keep_current_cover", reason=why)]
        return [_fc("buy_policy", plan_id=choice, reason=why)]
    bought = r.get("buy_policy") or {}
    if "message_someone" not in r.calls and isinstance(bought, dict) and bought.get("insurer"):
        friend = next((x for x in prof.get("people_you_know", []) if not x.get("employee") and x["id"].startswith("r")), None)
        if friend:
            ours = bought.get("insurer") == "aich"
            return [_fc("message_someone", resident_id=friend["id"], text=("I just joined AI Company Health - their dental and clinics look good value." if ours
                                                                         else "I just sorted my health insurance - worth comparing prices this year."))]
    return _text("Sorted my health insurance for now.")


def _town_campaign(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_town_insights")]
    if n == 1:
        ins = r.get("get_town_insights") or {}
        if ins.get("active_campaigns"):
            return _text("A campaign is already running; no new one this week.")
        aud = {"life_stage": ["family", "couple"], "age_min": 25, "age_max": 50}
        return [_fc("launch_town_campaign", title="Family cover with no-gap dental", message="Family Silver + Extras: no-gap check-ups at our dental clinics and fast claims.",
                    audience_json=json.dumps(aud), offer="6 weeks free for new joining families", weeks=4)]
    return _text("Town campaign launched.")



def _weekly_goals(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_weekly_goals")]
    if n == 1:
        goals = [{"metric": "new_sales", "target": 3, "owner": "sales.leo", "why": "Grow on last week"},
                 {"metric": "cancellations", "target": 0, "owner": "care.rafael", "why": "Keep every member"},
                 {"metric": "claims_sla_pct", "target": 92, "owner": "claims.helen", "why": "Service standard"}]
        return [_fc("set_weekly_goals", goals_json=json.dumps(goals))]
    return _text("Goals set for the week.")


def _council(agent: str, r: Replies, n: int, mock: dict) -> list[types.Part]:
    if n == 0:
        return [_fc("get_town_needs")]
    needs = r.get("get_town_needs") or {}
    if n == 1 and needs.get("options"):
        o = needs["options"][0]
        return [_fc("build_facility", kind=o["kind"], reason=f"{o['why']} (population {needs.get('population')})")]
    return _text("Nothing new to build this month." if n == 1 else "The council made its decision.")
