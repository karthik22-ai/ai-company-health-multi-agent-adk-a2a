"""The company as the agents see it: KPIs, alerts, the initiative book (propose → review → decide → run → evaluate), budget and pricing."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from hq.company import initiatives as im
from hq.company import rules
from hq.company.catalog import (
    ANNUAL_STRATEGY_BUDGET,
    DEPT_COSTS,
    TARGETS,
    VARIABLE_EXPENSE,
    industry_rate_rise,
)
from hq.company.store import Store
from hq.company.synthetic import CompanySim, DayResult

METRIC_DIRECTION = {"loss_ratio": -1, "claims_sla_pct": 1, "avg_wait_s": -1, "nps": 1, "net_adds": 1, "margin": 1, "engagement": 1}


class Company:
    def __init__(self, db_path: Path, seed: int = 7, start: date = date(2026, 3, 2), economy: str = "synthetic"):
        self.store = Store(db_path)
        self.seed, self.start = seed, start
        self.sim = CompanySim(self.store, seed, start)
        from hq.work.files import WorkFiles  # late import: work depends on biz.store only
        self.files = WorkFiles(self.store, lambda: self.today)
        from hq.town.town import Town
        self.town = Town(self.store, self)
        from hq.quality.goals import Goals
        from hq.quality.guard import FileGuard
        self.goals = Goals(self)
        self.guard = FileGuard(self)
        self.files.on_create = self.guard.on_create
        from hq.work.app_requests import AppRequests
        self.app_requests = AppRequests(self)
        from hq.quality import traces
        traces.ensure(self.store)
        self.economy_mode = economy
        self.economy = None
        if economy == "town":
            from hq.company.economy import TownEconomy
            self.economy = TownEconomy(self)
            self.economy.ensure()
        self.ids = int(self.store.get_kv("initiative_counter", 0))

    # ------------------------------------------------------------------ lifecycle
    def ensure_history(self, days: int = 365) -> bool:
        """Create a year of realistic history on first run. Returns True if it generated data. (Not used when the numbers come from the town agents.)"""
        if self.economy is not None:
            self._seed_products()
            return False
        if self.store.last_date():
            return False
        d = self.start - timedelta(days=days)
        while d < self.start:
            self.sim.step(d, history=True)
            d += timedelta(days=1)
        self.sim.s["budget"] = {"fy_year": self.start.year if self.start.month >= 7 else self.start.year - 1, "remaining": float(ANNUAL_STRATEGY_BUDGET)}
        self.store.commit()
        self.sim.save()
        self._seed_products()
        return True

    def _seed_products(self) -> None:
        for p in self.sim.products.values():
            self.store.db.execute("INSERT OR REPLACE INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                                  (p.id, p.name, p.category, p.tier, p.price, int(p.active), p.launched, p.target, p.description, json.dumps(p.inclusions), p.waiting))
        self.store.commit()

    @property
    def today(self) -> date:
        return self.sim.today

    def advance(self) -> DayResult:
        """Simulate the next day. Rolls the strategy budget over on 1 July."""
        d = self.today + timedelta(days=1)
        if d.month == 7 and d.day == 1:
            self.sim.s["budget"] = {"fy_year": d.year, "remaining": float(ANNUAL_STRATEGY_BUDGET) * (1 / 4000 if self.economy is not None else 1)}
        res = self.economy.step(d) if self.economy is not None else self.sim.step(d)
        self.store.commit()
        self._sync_initiatives()
        self._seed_products()
        self.sim.save()
        return res

    # ------------------------------------------------------------------ KPI views
    def kpi_window(self, days: int = 7, end: str | None = None) -> dict[str, Any]:
        end = end or self.store.last_date()
        cur = self.store.kpis(days, end)
        prev_end = (date.fromisoformat(cur[0]["date"]) - timedelta(days=1)).isoformat() if cur else end
        prev = self.store.kpis(days, prev_end)
        if not cur:
            return {}

        def agg(rows: list[dict[str, Any]]) -> dict[str, float]:
            n = len(rows)
            rev = sum(r["premium_revenue"] for r in rows) or 1.0
            return {
                "policies_in_force": rows[-1]["policies_in_force"],
                "new_sales_per_day": sum(r["new_sales"] for r in rows) / n,
                "cancellations_per_day": sum(r["cancellations"] for r in rows) / n,
                "net_adds": sum(r["net_adds"] for r in rows) / n,
                "leads_per_day": sum(r["leads"] for r in rows) / n,
                "conversion": sum(r["new_sales"] for r in rows) / max(sum(r["leads"] for r in rows), 1),
                "premium_revenue_per_day": rev / n,
                "loss_ratio": sum(r["claims_incurred"] for r in rows) / rev,
                "margin": sum(r["margin"] * r["premium_revenue"] for r in rows) / rev,
                "claims_sla_pct": sum(r["claims_sla_pct"] for r in rows) / n,
                "claims_backlog": rows[-1]["claims_backlog"],
                "claims_utilization": sum(r["utilization_claims"] for r in rows) / n,
                "avg_wait_s": sum(r["avg_wait_s"] for r in rows) / n,
                "abandon_pct": sum(r["abandon_pct"] for r in rows) / n,
                "care_utilization": sum(r["utilization_care"] for r in rows) / n,
                "csat": sum(r["csat"] for r in rows) / n,
                "nps": rows[-1]["nps"],
                "brand_awareness": rows[-1]["brand_awareness"],
                "headcount": rows[-1]["headcount"],
                "engagement": rows[-1]["engagement"],
                "exits_per_day": sum(r["exits"] for r in rows) / n,
                "initiative_cost_per_day": sum(r["initiative_cost"] for r in rows) / n,
            }

        a, b = agg(cur), (agg(prev) if prev else {})
        change = {k: ((a[k] - b[k]) / abs(b[k]) if b and b.get(k) else None) for k in a}
        status = {}
        for k, t in TARGETS.items():
            key = {"claims_sla_pct": "claims_sla_pct", "net_adds": "net_adds"}.get(k, k)
            v = a.get(key)
            if v is not None:
                status[k] = {"value": round(v, 4), "target": t, "ok": (v * METRIC_DIRECTION[k] >= t * METRIC_DIRECTION[k])}
        return {"window_days": days, "from": cur[0]["date"], "to": cur[-1]["date"], "current": {k: round(v, 4) for k, v in a.items()},
                "previous": {k: round(v, 4) for k, v in b.items()}, "change_pct": {k: (round(v * 100, 1) if v is not None else None) for k, v in change.items()},
                "targets": status}

    def breakdown(self, by: str, days: int = 28, metric: str = "sales") -> list[dict[str, Any]]:
        end = self.store.last_date() or self.today.isoformat()
        table, col, dim = {"sales": ("daily_sales", "sales", {"state": "state", "channel": "channel", "product": "product_id"}),
                           "claims": ("daily_claims", "claims", {"state": "state", "claim_type": "claim_type"}),
                           "cancellations": ("daily_cancellations", "cancellations", {"product": "product_id", "reason": "reason"})}.get(metric, (None, None, None))
        if not table or by not in dim:
            return [{"error": f"metric must be sales|claims|cancellations; by options for {metric}: {sorted(dim or {})}"}]
        extra = ", ROUND(SUM(benefits_aud)) AS benefits_aud" if metric == "claims" else (", ROUND(SUM(new_premium_pa)) AS new_premium_pa" if metric == "sales" else "")
        sql = (f"SELECT {dim[by]} AS {by}, SUM({col}) AS total{extra} FROM {table} WHERE date > date(?, ?) AND date <= ? GROUP BY 1 ORDER BY total DESC")
        rows = self.store.rows(sql, (end, f"-{days} day", end))
        if by == "age_band":
            return rows
        tot = sum(r["total"] for r in rows) or 1
        for r in rows:
            r["share_pct"] = round(r["total"] / tot * 100, 1)
        return rows

    def sales_by_age(self, days: int = 28) -> list[dict[str, Any]]:
        end = self.store.last_date() or self.today.isoformat()
        return self.store.rows("SELECT age_band, SUM(sales) AS total FROM daily_sales_age WHERE date > date(?, ?) AND date <= ? GROUP BY 1 ORDER BY 1",
                               (end, f"-{days} day", end))

    def forecast(self, metric: str = "new_sales", horizon: int = 7) -> dict[str, Any]:
        """Seasonal-naive forecast: same weekdays last year, scaled by this year's trend."""
        if metric not in ("new_sales", "cancellations", "leads", "claims_arrivals", "calls"):
            return {"error": "metric must be new_sales, cancellations, leads, claims_arrivals or calls"}
        end = date.fromisoformat(self.store.last_date() or self.today.isoformat())
        def total(a: date, b: date) -> float:
            r = self.store.one(f"SELECT SUM({metric}) v FROM daily_kpi WHERE date>? AND date<=?", (a.isoformat(), b.isoformat()))
            return (r or {}).get("v") or 0.0
        this28, last28 = total(end - timedelta(days=28), end), total(end - timedelta(days=28 + 364), end - timedelta(days=364))
        trend = this28 / last28 if last28 else 1.0
        days = []
        for i in range(1, horizon + 1):
            d = end + timedelta(days=i)
            ly = self.store.one(f"SELECT {metric} v FROM daily_kpi WHERE date=?", ((d - timedelta(days=364)).isoformat(),))
            days.append({"date": d.isoformat(), "forecast": round((ly or {}).get("v", 0) * trend, 1)})
        return {"metric": metric, "trend_vs_last_year": round(trend, 3), "days": days, "total": round(sum(x["forecast"] for x in days), 1)}

    # ------------------------------------------------------------------ alerts (rule based; the daily review reads these)
    def alerts(self) -> list[dict[str, Any]]:
        w7, w28 = self.kpi_window(7), self.kpi_window(28)
        if not w7:
            return []
        c7, c28 = w7["current"], w28["current"]
        out: list[dict[str, Any]] = []

        def add(key: str, dept: str, sev: str, metric: str, value: float, thr: float, msg: str) -> None:
            out.append({"key": key, "dept": dept, "severity": sev, "metric": metric, "value": round(value, 3), "threshold": thr, "message": msg})

        if c7["claims_sla_pct"] < TARGETS["claims_sla_pct"]:
            add("claims_sla", "claims", "high" if c7["claims_sla_pct"] < 85 else "medium", "claims_sla_pct", c7["claims_sla_pct"], TARGETS["claims_sla_pct"],
                f"Only {c7['claims_sla_pct']:.1f}% of claims assessed within 5 business days (target {TARGETS['claims_sla_pct']:.0f}%); backlog {c7['claims_backlog']:,.0f}.")
        if c7["avg_wait_s"] > TARGETS["avg_wait_s"]:
            add("call_wait", "care", "high" if c7["avg_wait_s"] > 300 else "medium", "avg_wait_s", c7["avg_wait_s"], TARGETS["avg_wait_s"],
                f"Average wait {c7['avg_wait_s']:.0f}s (target {TARGETS['avg_wait_s']:.0f}s), {c7['abandon_pct']:.1f}% of calls abandoned.")
        if c28["new_sales_per_day"] and (c7["new_sales_per_day"] / c28["new_sales_per_day"] - 1) < -0.12:
            add("sales_drop", "sales", "medium", "new_sales_per_day", c7["new_sales_per_day"], c28["new_sales_per_day"] * 0.88,
                f"New sales {c7['new_sales_per_day']:.0f}/day are {abs(c7['new_sales_per_day']/c28['new_sales_per_day']-1)*100:.0f}% below the 28-day average (seasonality may explain part).")
        if c28["net_adds"] < TARGETS["net_adds"]:
            add("net_adds", "sales", "low", "net_adds", c28["net_adds"], TARGETS["net_adds"], f"Net policy growth {c28['net_adds']:.0f}/day vs target {TARGETS['net_adds']:.0f}/day.")
        if c28["loss_ratio"] > TARGETS["loss_ratio"] + 0.015:
            add("loss_ratio", "data", "high" if c28["loss_ratio"] > 0.9 else "medium", "loss_ratio", c28["loss_ratio"], TARGETS["loss_ratio"],
                f"28-day loss ratio {c28['loss_ratio']*100:.1f}% (target ≤ {TARGETS['loss_ratio']*100:.0f}%).")
        if c28["margin"] < TARGETS["margin"] * 0.5:
            add("margin", "exec", "medium", "margin", c28["margin"], TARGETS["margin"], f"28-day operating margin {c28['margin']*100:.1f}% (target {TARGETS['margin']*100:.0f}%).")
        if c7["nps"] < 20:
            add("nps", "care", "medium", "nps", c7["nps"], 20, f"NPS has fallen to {c7['nps']:.0f}.")
        if c7["engagement"] < 65:
            add("engagement", "people", "medium", "engagement", c7["engagement"], 65, f"Staff engagement {c7['engagement']:.0f} (target {TARGETS['engagement']:.0f}).")
        for dept, t in self.team_status().items():
            if t["utilization"] > 1.05 and dept in ("claims", "care", "sales"):
                add(f"capacity_{dept}", dept, "medium", "utilization", t["utilization"], 1.05, f"{dept} team is over capacity ({t['utilization']*100:.0f}% utilised).")
            if t["attrition_annualised"] > 0.26 and t["exits_90d"] >= 3:
                add(f"attrition_{dept}", "people", "medium", "attrition", t["attrition_annualised"], 0.26, f"{dept} attrition is running at {t['attrition_annualised']*100:.0f}% a year.")
        for e in self.sim.s["events"]:
            out.append({"key": f"event_{e['type']}", "dept": "data", "severity": "info", "metric": "event", "value": 0, "threshold": 0, "message": f"Market event: {e['name']} – {e['desc']}"})
        order = {"high": 0, "medium": 1, "low": 2, "info": 3}
        return sorted(out, key=lambda a: order[a["severity"]])

    # ------------------------------------------------------------------ team
    def team_status(self) -> dict[str, dict[str, Any]]:
        end = self.store.last_date()
        out: dict[str, dict[str, Any]] = {}
        for dept, t in self.sim.s["team"].items():
            r = self.store.one("SELECT SUM(exits) e, AVG(utilization) u, AVG(engagement) g FROM daily_team WHERE dept=? AND date>date(?, '-90 day')", (dept, end)) if end else {}
            exits90 = (r or {}).get("e") or 0
            pipeline = sum(x[0] for x in t["pipeline"])
            out[dept] = {"dept": dept, "headcount": round(t["staff"], 1), "open_roles": pipeline, "utilization": round((r or {}).get("u") or t["util"], 3),
                         "engagement": round(t["engagement"], 1), "attrition_annualised": round(exits90 / 90 * 365 / max(t["staff"], 1), 3), "exits_90d": int(exits90),
                         "productivity": t["prod"], "starters_ramping": sum(n for n, _ in t["ramp"]),
                         "annual_cost": round(t["staff"] * DEPT_COSTS[dept].salary), "next_arrivals": sorted([[n, d] for n, d, _ in t["pipeline"]], key=lambda x: x[1])[:3]}
        return out

    # ------------------------------------------------------------------ products
    def products_view(self) -> list[dict[str, Any]]:
        end = self.store.last_date()
        sales = {r["product_id"]: r["n"] for r in self.store.rows("SELECT product_id, SUM(sales) n FROM daily_sales WHERE date>date(?, '-28 day') GROUP BY 1", (end,))} if end else {}
        canc = {r["product_id"]: r["n"] for r in self.store.rows("SELECT product_id, SUM(cancellations) n FROM daily_cancellations WHERE date>date(?, '-28 day') GROUP BY 1", (end,))} if end else {}
        out = []
        for p in self.sim.products.values():
            inf = self.sim.s["in_force"].get(p.id, 0.0)
            price = p.price * self.sim.s["price_idx"].get(p.id, 1.0)
            out.append({"id": p.id, "name": p.name, "category": p.category, "tier": p.tier, "monthly_price": round(price, 2), "in_force": round(inf),
                        "sales_28d": sales.get(p.id, 0), "cancellations_28d": canc.get(p.id, 0), "claims_ratio_plan": p.claims_ratio, "target": p.target,
                        "description": p.description, "inclusions": p.inclusions, "waiting": p.waiting, "launched": p.launched, "active": p.active,
                        "price_vs_market": round(self.sim.s["price_idx"].get(p.id, 1.0) / self.sim.s["market_idx"], 3)})
        return out

    def unit_economics(self, product_id: str | None = None) -> dict[str, Any]:
        """Customer lifetime value vs cost of acquisition (what a CFO would ask before approving growth spend)."""
        prods = [self.sim.products[product_id]] if product_id else list(self.sim.products.values())
        rows = []
        for p in prods:
            if p.id not in self.sim.products:
                return {"error": f"unknown product {product_id}"}
            pa = p.price * self.sim.s["price_idx"].get(p.id, 1.0) * 12
            contrib = pa * (1 - p.claims_ratio * 0.955 - VARIABLE_EXPENSE) + pa * 0.012
            life = 1 / max(p.lapse, 0.02)
            rows.append({"product": p.id, "annual_premium": round(pa), "annual_contribution": round(contrib), "expected_lifetime_years": round(life, 1),
                         "lifetime_value": round(contrib * min(life, 8) * 0.85)})
        return {"products": rows, "note": "LTV is undiscounted-ish contribution over min(expected life, 8y) with a 15% haircut; compare it with cost per policy won."}

    # ------------------------------------------------------------------ initiative book
    def _next_id(self) -> str:
        self.ids += 1
        self.store.set_kv("initiative_counter", self.ids)
        return f"I{self.ids}"

    def budget(self) -> dict[str, Any]:
        b = self.sim.s["budget"]
        committed = sum(i["cost_est"] for i in self.sim.initiatives.values() if i["status"] in ("approved", "running", "completed")
                        and i.get("decided", "") >= f"{b['fy_year']}-07-01")
        annual = ANNUAL_STRATEGY_BUDGET * (1 / 4000 if self.economy is not None else 1)
        return {"financial_year": f"FY{(b['fy_year'] + 1) % 100:02d}", "annual_strategy_budget": round(annual), "remaining": round(b["remaining"]),
                "committed_this_year": round(committed), "note": "One-off and campaign costs only; hiring adds ongoing payroll shown as run_rate_annual."}

    def propose(self, proposer: str, dept: str, kind: str, title: str, rationale: str, params: dict[str, Any]) -> dict[str, Any]:
        clean, errs = im.validate_params(kind, params, set(self.sim.products))
        if errs:
            return {"error": "; ".join(errs), "kind_help": im.KIND_HELP.get(kind)}
        ctx = self.sim.context()
        est = im.estimate(kind, clean, ctx)
        if self.economy is not None:
            from hq.company.economy import SCALE
            est = dict(est, cost=est["cost"] * SCALE, note="costs scaled to the Wattle Grove market")
        comp = rules.check_initiative(kind, clean, f"{title} {rationale}", est["cost"], {"budget_remaining": self.sim.s["budget"]["remaining"], "headcount": ctx["headcount"]})
        ini = {"id": self._next_id(), "title": title[:120], "kind": kind, "params": clean, "status": "proposed", "proposer": proposer, "dept": dept,
               "rationale": rationale[:800], "estimate": est, "cost_est": round(est["cost"]), "compliance": comp.to_dict(), "reviews": [], "created": self.today.isoformat(),
               "decided": None, "start_date": None, "end_date": None, "decision_note": "", "decided_by": ""}
        self.sim.initiatives[ini["id"]] = ini
        self._save(ini)
        return ini

    def review(self, ini_id: str, reviewer: str, verdict: str, comments: str) -> dict[str, Any]:
        ini = self.sim.initiatives.get(ini_id)
        if not ini:
            return {"error": f"unknown initiative {ini_id}"}
        if ini["status"] not in ("proposed", "in_review"):
            return {"error": f"initiative is {ini['status']}; it can no longer be reviewed"}
        ini["reviews"].append({"by": reviewer, "verdict": verdict, "comments": comments[:500], "date": self.today.isoformat()})
        ini["status"] = "in_review"
        self._save(ini)
        return ini

    def decide(self, ini_id: str, decider: str, decision: str, note: str) -> dict[str, Any]:
        ini = self.sim.initiatives.get(ini_id)
        if not ini:
            return {"error": f"unknown initiative {ini_id}"}
        if ini["status"] not in ("proposed", "in_review"):
            return {"error": f"initiative is already {ini['status']}"}
        if decision == "approve":
            ctx = self.sim.context()
            comp = rules.check_initiative(ini["kind"], ini["params"], f"{ini['title']} {ini['rationale']}", ini["cost_est"],
                                          {"budget_remaining": self.sim.s["budget"]["remaining"], "headcount": ctx["headcount"]})
            ini["compliance"] = comp.to_dict()
            if not comp.ok:
                return {"error": "cannot approve: " + " ".join(comp.violations), "compliance": comp.to_dict()}
            self.sim.s["budget"]["remaining"] -= ini["cost_est"]
            ini["decided"] = self.today.isoformat()
            ini["decided_by"], ini["decision_note"] = decider, note[:500]
            self.sim.schedule(ini, self.today)
        else:
            ini["status"] = "rejected"
            ini["decided"], ini["decided_by"], ini["decision_note"] = self.today.isoformat(), decider, note[:500]
        self._save(ini)
        self.sim.save()
        return ini

    def cancel(self, ini_id: str, by: str, note: str = "") -> dict[str, Any]:
        ini = self.sim.initiatives.get(ini_id)
        if not ini or ini["status"] not in ("approved", "running"):
            return {"error": "only approved or running initiatives can be cancelled"}
        ini["status"], ini["decision_note"] = "cancelled", f"{ini['decision_note']} | cancelled by {by}: {note}"
        self._save(ini)
        return ini

    def list_initiatives(self, status: str | None = None, dept: str | None = None) -> list[dict[str, Any]]:
        items = [i for i in self.sim.initiatives.values() if (not status or i["status"] == status) and (not dept or i["dept"] == dept or i["proposer"].startswith(dept))]
        return sorted(items, key=lambda i: int(i["id"][1:]), reverse=True)

    def _save(self, ini: dict[str, Any]) -> None:
        self.store.db.execute("INSERT OR REPLACE INTO initiatives VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                              (ini["id"], ini["title"], ini["kind"], ini["status"], ini["proposer"], ini["dept"], ini["cost_est"], ini["created"], ini["decided"],
                               ini["start_date"], ini["end_date"], json.dumps(ini)))
        self.store.commit()

    def _sync_initiatives(self) -> None:
        for ini in self.sim.initiatives.values():
            self._save(ini)

    # ------------------------------------------------------------------ evaluation of running/finished initiatives
    def evaluate(self, ini_id: str) -> dict[str, Any]:
        """Before/after on the metrics the initiative should move, de-seasonalised with a difference-in-differences vs last year."""
        ini = self.sim.initiatives.get(ini_id)
        if not ini:
            return {"error": f"unknown initiative {ini_id}"}
        if not ini.get("start_date") or ini["start_date"] > self.today.isoformat():
            return {"initiative": ini_id, "status": ini["status"], "message": "has not started yet, nothing to evaluate"}
        start = date.fromisoformat(ini["start_date"])
        end = min(self.today, date.fromisoformat(ini["end_date"])) if ini.get("end_date") else self.today
        days = max((end - start).days, 1)
        before_a, before_b = start - timedelta(days=min(28, days + 14)), start
        kind, p = ini["kind"], ini["params"]
        metrics: dict[str, tuple[str, str]] = {
            "marketing_campaign": ("leads", "new_sales"), "promo_discount": ("new_sales", "conversion"), "new_product": ("new_sales",),
            "hire": ("claims_sla_pct", "avg_wait_s", "net_adds"), "training": ("claims_sla_pct", "avg_wait_s"), "wellbeing_program": ("engagement", "exits"),
            "automation": ("claims_sla_pct", "avg_wait_s", "utilization_claims"), "provider_deal": ("loss_ratio",), "retention_program": ("cancellations",),
            "preventive_program": ("loss_ratio",), "broker_commission": ("new_sales",)}[kind]

        def mean(col: str, a: date, b: date, shift: int = 0) -> float | None:
            r = self.store.one(f"SELECT AVG({col}) v FROM daily_kpi WHERE date>? AND date<=?", ((a - timedelta(days=shift)).isoformat(), (b - timedelta(days=shift)).isoformat()))
            return (r or {}).get("v")

        res: dict[str, Any] = {}
        for m in metrics:
            b0, a0 = mean(m, before_a, before_b), mean(m, start, end)
            b1, a1 = mean(m, before_a, before_b, 364), mean(m, start, end, 364)
            if None in (b0, a0):
                continue
            naive = (a0 - b0) / abs(b0) if b0 else None
            did = None
            if None not in (b1, a1) and b1:
                did = naive - (a1 - b1) / abs(b1) if naive is not None else None
            res[m] = {"before": round(b0, 3), "after": round(a0, 3), "change_pct_naive": None if naive is None else round(naive * 100, 1),
                      "change_pct_vs_last_year_pattern": None if did is None else round(did * 100, 1)}
        return {"initiative": ini_id, "title": ini["title"], "status": ini["status"], "kind": kind, "start": ini["start_date"], "evaluated_to": end.isoformat(),
                "days_in": days, "expected": ini["estimate"]["headline"], "expected_cost": ini["cost_est"], "metrics": res,
                "caveat": "Seasonality is partly removed using last year's pattern; other initiatives and market events overlap, so treat as indicative."}

    # ------------------------------------------------------------------ premium round (the one time existing members' prices may change)
    def premium_round_context(self) -> dict[str, Any]:
        yr = self.today.year if (self.today.month, self.today.day) <= (4, 1) else self.today.year + 1
        eff = date(yr, 4, 1)
        cap = industry_rate_rise(yr)
        weights = {p.id: self.sim.s["in_force"].get(p.id, 0) * p.price for p in self.sim.products.values()}
        return {"effective": eff.isoformat(), "days_to_go": (eff - self.today).days, "industry_approved_average_cap": cap,
                "market_index": round(self.sim.s["market_idx"], 4), "weights": weights}

    def submit_premium_round(self, decider: str, changes: dict[str, float]) -> dict[str, Any]:
        ctx = self.premium_round_context()
        eff = date.fromisoformat(ctx["effective"])
        res = rules.check_premium_round(changes, ctx["weights"], ctx["industry_approved_average_cap"], eff, self.today)
        if not res.ok:
            return {"error": " ".join(res.violations), "warnings": res.warnings}
        self.sim.schedule_price_changes(changes, eff)
        self.sim.save()
        wsum = sum(ctx["weights"].values()) or 1
        avg = sum(changes.get(p, 0) * w for p, w in ctx["weights"].items()) / wsum
        return {"ok": True, "effective": ctx["effective"], "weighted_average_increase": round(avg, 4), "warnings": res.warnings, "decided_by": decider}

    # ------------------------------------------------------------------ misc views for the dashboard
    def series(self, metric: str, days: int = 60) -> list[dict[str, Any]]:
        if metric not in __import__("hq.company.store", fromlist=["KPI_COLUMNS"]).KPI_COLUMNS:
            return []
        return [{"date": r["date"], "value": r[metric]} for r in self.store.kpis(days)]

    def snapshot(self) -> dict[str, Any]:
        """Everything the dashboard header needs in one object."""
        last = self.store.kpis(1)
        w7 = self.kpi_window(7)
        return {"date": self.today.isoformat(), "last": last[0] if last else None, "week": w7.get("current", {}), "targets": w7.get("targets", {}),
                "events": self.sim.s["events"], "budget": self.budget(), "alerts": [a for a in self.alerts() if a["severity"] != "info"][:6],
                "initiatives": {s: sum(1 for i in self.sim.initiatives.values() if i["status"] == s) for s in im.STATUSES}}

    # ------------------------------------------------------------------ dashboard / UI payloads
    def public_initiative(self, ini: dict[str, Any]) -> dict[str, Any]:
        keep = {k: ini.get(k) for k in ("id", "title", "kind", "status", "proposer", "dept", "cost_est", "created", "decided", "start_date", "end_date",
                                        "rationale", "decision_note", "decided_by")}
        keep["headline"] = ini.get("estimate", {}).get("headline", "")
        keep["compliance"] = ini.get("compliance", {})
        keep["reviews"] = ini.get("reviews", [])
        return keep

    def recent_notes(self, limit: int = 30, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            return self.store.rows("SELECT * FROM notes WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, limit))
        return self.store.rows("SELECT * FROM notes ORDER BY id DESC LIMIT ?", (limit,))

    def dept_kpis(self) -> dict[str, list[list[str]]]:
        w = self.kpi_window(7)
        if not w:
            return {}
        c = w["current"]
        team = self.team_status()
        ini = self.sim.initiatives
        running = sum(1 for i in ini.values() if i["status"] in ("approved", "running"))
        promos = sum(1 for i in ini.values() if i["kind"] == "promo_discount" and i["status"] in ("approved", "running"))
        fc = self.forecast("new_sales", 7).get("total", 0)
        pr = self.premium_round_context()
        review = sum(1 for i in ini.values() if i["status"] in ("proposed", "in_review"))
        blocked = sum(1 for i in ini.values() if i["status"] == "rejected" and not (i.get("compliance") or {}).get("ok", True))
        fmt = lambda v, f: f.format(v)  # noqa: E731
        fc_ = self.files.counts()
        return {
            "exec": [["Net adds / day", f"{c['net_adds']:+.0f}"], ["Margin", f"{c['margin']*100:.1f}%"], ["Initiatives live", str(running)]],
            "sales": [["Sales / day", f"{c['new_sales_per_day']:.0f}"], ["Conversion", f"{c['conversion']*100:.1f}%"], ["Leads / day", f"{c['leads_per_day']:,.0f}"]],
            "mkt": [["Leads / day", f"{c['leads_per_day']:,.0f}"], ["Awareness", f"{c['brand_awareness']:.0f}"], ["Cancel / day", f"{c['cancellations_per_day']:.0f}"]],
            "data": [["Loss ratio", f"{c['loss_ratio']*100:.1f}%"], ["7-day sales fcst", f"{fc:,.0f}"], ["Policies", f"{c['policies_in_force']/1000:,.1f}k"]],
            "claims": [["Within SLA", f"{c['claims_sla_pct']:.0f}%"], ["Backlog", f"{c['claims_backlog']:,.0f}"], ["Utilisation", f"{c['claims_utilization']*100:.0f}%"]],
            "care": [["Wait", f"{c['avg_wait_s']:.0f}s"], ["CSAT", f"{c['csat']:.0f}"], ["NPS", f"{c['nps']:.0f}"]],
            "health": [["Programs live", str(sum(1 for i in ini.values() if i['kind'] in ('preventive_program', 'provider_deal') and i['status'] in ('approved', 'running')))],
                       ["Loss ratio", f"{c['loss_ratio']*100:.1f}%"], ["Staff", f"{team['health']['headcount']:.0f}"]],
            "people": [["Headcount", f"{c['headcount']:.0f}"], ["Engagement", f"{c['engagement']:.0f}"], ["Exits / day", f"{c['exits_per_day']:.1f}"]],
            "prod": [["Active plans", str(sum(1 for p in self.sim.products.values() if p.active))], ["Premium round", f"{pr['days_to_go']}d"], ["Promos live", str(promos)]],
            "risk": [["Under review", str(review)], ["Blocked (rules)", str(blocked)], ["Open alerts", str(len([a for a in self.alerts() if a['severity'] != 'info']))]],
            "bi": [["Dashboards", str(fc_.get("dashboard", 0))], ["Reports", str(fc_.get("report", 0) + fc_.get("minutes", 0))], ["Decks", str(fc_.get("presentation", 0))]],
            "it": [["Apps live", str(fc_.get("app", 0))], ["App backlog", str(sum(v for s, v in self.app_requests.counts().items() if s in ("open", "planned", "building")))],
                   ["Access requests", str(len(self.files.access_requests("pending")))]],
        }

    def sales(self, recent: int = 25) -> dict[str, Any]:
        """Memberships sold (residents who bought or switched to us) and lost (switched away), from the residents' own decisions."""
        import json as _json
        from hq.town.town import INSURERS
        st, today = self.store, self.today
        ev = st.rows("SELECT * FROM town_events WHERE kind IN ('buy','switch') ORDER BY id DESC")
        nm = lambda rid: (self.town.resident(rid) or {}).get("name", rid)  # noqa: E731
        sold, lost = [], []
        for e in ev:
            d = _json.loads(e["data"] or "{}")
            row = {"date": e["date"], "resident": e["resident"], "name": nm(e["resident"]), "plan": e["plan"], "price_month": d.get("price"),
                   "from": INSURERS.get(d.get("before_insurer") or "", {}).get("name") or ("no cover" if e["kind"] == "buy" else d.get("before_insurer")),
                   "to": INSURERS.get(e["insurer"] or "", {}).get("name", e["insurer"]), "why": (d.get("reason") or e["text"] or "")[:200]}
            if e["insurer"] == "aich":
                sold.append(row)
            elif d.get("before_insurer") == "aich":
                lost.append(row)

        def count(rows: list, days: int) -> int:
            since = (today - timedelta(days=days)).isoformat()
            return sum(1 for r in rows if r["date"] >= since)
        return {"sold": {"today": count(sold, 0), "7d": count(sold, 7), "28d": count(sold, 28), "all_time": len(sold)},
                "lost": {"today": count(lost, 0), "7d": count(lost, 7), "28d": count(lost, 28), "all_time": len(lost)},
                "members_now": sum(1 for r in self.town.residents() if (r.get("cover") or {}).get("insurer") == "aich"),
                "recent_sales": sold[:recent], "recent_losses": lost[:recent]}

    def profile(self) -> dict[str, Any]:
        """Everything about the company in one place: who we are, our people, our health care, our plans, our market position."""
        from hq.agents.roster import DEPARTMENTS
        from hq.town.town import INSURER_NOTE, INSURERS
        res = self.town.residents()
        share: dict[str, int] = {}
        for r in res:
            k = (r.get("cover") or {}).get("insurer") or "none"
            share[k] = share.get(k, 0) + 1
        rank = sorted(share.items(), key=lambda x: -x[1])
        k = (self.kpi_window(28) or {}).get("current", {})
        lev = self.economy.levers() if self.economy else {}
        return {
            "name": "AI Company Health", "type": "Private health insurer with its own hospital and clinic",
            "sales": self.sales(12),
            "about": ("An Australian private health insurer operating in Wattle Grove. Health insurance membership is mandatory in the town and residents "
                      "choose between us and the real Australian funds. We also run the AI Company Health Private Hospital and the AI Company Health "
                      "Clinic (GP, dental, optical, physio), where members pay no gap."),
            "headquarters": "AI Company HQ, three floors, Wattle Grove", "health_care": ["AI Company Health Private Hospital", "AI Company Health Clinic"],
            "today": self.today.isoformat(),
            "members": share.get("aich", 0), "town_population": len(res), "market_share": round(share.get("aich", 0) / max(1, len(res)), 3),
            "market_rank": next((i + 1 for i, (key, _) in enumerate(rank) if key == "aich"), None),
            "market": [{"fund": INSURERS.get(key, {}).get("name", key), "id": key, "people": n} for key, n in rank], "market_note": INSURER_NOTE,
            "kpis_28d": {x: k.get(x) for x in ("policies_in_force", "new_sales_per_day", "cancellations_per_day", "premium_revenue_per_day", "loss_ratio",
                                                  "margin", "claims_sla_pct", "avg_wait_s", "nps")},
            "offers_and_perks": {"new_member_discount": lev.get("new_joiner_discount", 0), "perks": lev.get("perks", []),
                                 "group_deals": lev.get("group_employers", [])},
            "plans": [{x: p[x] for x in ("id", "name", "category", "tier", "monthly_price", "in_force")} for p in self.products_view() if p["active"]],
            "leadership": [{"id": a.id, "name": a.name, "role": a.role} for d in DEPARTMENTS.values() for a in d.agents if a.lead],
            "departments": [{"id": d.id, "name": d.name, "head": d.lead_name, "agents": len(d.agents), "mission": d.mission} for d in DEPARTMENTS.values()],
            "budget": self.budget(),
            "initiatives_live": [{"id": i["id"], "title": i["title"], "kind": i["kind"]} for i in self.sim.initiatives.values() if i.get("status") in ("approved", "running")],
        }

    def dashboard_payload(self) -> dict[str, Any]:
        snap = self.snapshot()
        snap["dept_kpis"] = self.dept_kpis()
        snap["series"] = {m: self.series(m, 60) for m in ("new_sales", "cancellations", "net_adds", "loss_ratio", "margin", "claims_sla_pct", "claims_backlog", "avg_wait_s", "nps", "engagement", "policies_in_force")}
        snap["team"] = self.team_status()
        snap["products"] = self.products_view()
        return snap

    def close(self) -> None:
        self.store.close()
