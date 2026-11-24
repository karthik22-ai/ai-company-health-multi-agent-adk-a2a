"""The company's numbers come ONLY from what the agents do in Wattle Grove (this replaces the synthetic data generator).

Every day:
  members / policies   = residents (households) whose fund is AI Company Health
  new sales / leavers  = residents who joined / switched away that day
  leads, conversion    = residents who reviewed their cover or called us, and how many joined
  premium revenue      = what our member households pay (their real plan prices)
  claims               = what our members claimed when they used health care (visits in the town), at our own hospital/clinic or elsewhere
  service              = claims and calls handled by the Claims and Member Care agents; reviews written by residents
  costs                = management expenses, marketing campaigns and approved initiatives (scaled to the town)

Approved initiatives become levers the residents actually see: new-member discounts, perks, group deals at workplaces, faster service,
campaigns that reach people. The tables keep their usual shape (daily_kpi, daily_sales, daily_claims, ...), so every dashboard and tool works.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from hq.agents.roster import AGENTS, DEPARTMENTS
from hq.company.catalog import ANNUAL_STRATEGY_BUDGET, TARGETS
from hq.company.synthetic import DayResult
from hq.town.health import booked

SCALE = 1 / 4000                 # the town is a small market: budgets and initiative costs are scaled to it
TOWN_TARGETS = {"loss_ratio": 0.85, "claims_sla_pct": 92.0, "avg_wait_s": 120.0, "nps": 30.0, "net_adds": 0.25, "margin": 0.04, "engagement": 70.0}


class TownEconomy:
    def __init__(self, company: Any):
        self.co = company
        TARGETS.update(TOWN_TARGETS)

    # ------------------------------------------------------------------ switch the company to agent-driven data (once)
    def ensure(self) -> None:
        st = self.co.store
        if st.get_kv("economy") == "town":
            self.rebook()
            return
        for t in ("daily_leads", "daily_sales", "daily_sales_age", "daily_cancellations", "daily_claims", "daily_book", "daily_team", "daily_kpi", "events", "initiatives"):
            st.db.execute(f"DELETE FROM {t}")
        st.commit()
        self.co.sim.initiatives.clear()
        s = self.co.sim.s
        s["events"], s["pending_prices"] = [], []
        s["budget"] = {"fy_year": self.co.today.year if self.co.today.month >= 7 else self.co.today.year - 1, "remaining": float(ANNUAL_STRATEGY_BUDGET) * SCALE}
        st.set_kv("economy", "town")
        st.set_kv("claims_booking", "v3")
        st.set_kv("claims_backlog", 0)
        self.co.sim.save()
        self.co._seed_products()

    def rebook(self) -> None:
        """Once: recompute claims, loss ratio and margin of days already recorded with the old booking (every visit at full cost)."""
        st = self.co.store
        if st.get_kv("claims_booking") == "v3":
            return
        rows = st.rows("SELECT * FROM daily_kpi ORDER BY date")
        health = self.co.town.health
        for i, k in enumerate(rows):
            k["claims_incurred"] = round(health.booked_cost("aich", k["date"], estimate=True), 2)
            win = rows[max(0, i - 27):i + 1]
            prem28, claim28 = sum(w["premium_revenue"] for w in win), sum(w["claims_incurred"] for w in win)
            k["loss_ratio"] = round(claim28 / prem28, 4) if prem28 else 0.0
            p = k["premium_revenue"]
            k["margin"] = round((p - k["claims_incurred"] - k["opex"] - k["initiative_cost"] - k["marketing_spend"]) / p, 4) if p else 0.0
            st.insert_kpi(k)
        st.db.execute("DELETE FROM daily_claims")
        for c in st.rows("SELECT * FROM town_claims WHERE insurer='aich'"):
            if st.rows("SELECT 1 FROM daily_kpi WHERE date=?", (c["date"],)):
                r = self.co.town.resident(c["resident"]) or {}
                st.db.execute("INSERT INTO daily_claims VALUES (?,?,?,?,?)", (c["date"], r.get("suburb", ""), c["kind"], 1,
                                                                              round(booked(c["insurer_cost"], health.exposure(c["date"], True)), 2)))
        st.set_kv("claims_booking", "v3")
        st.commit()

    # ------------------------------------------------------------------ what approved initiatives change for residents
    def levers(self) -> dict[str, Any]:
        d = self.co.today.isoformat()
        lev: dict[str, Any] = {"new_joiner_discount": 0.0, "perks": [], "service_boost": 0.0, "group_employers": [], "group_discount": 0.0,
                               "campaign_boost": 0.0, "retention": False, "capacity": {"claims": 0, "care": 0}}
        for i in self.co.sim.initiatives.values():
            if i.get("status") not in ("approved", "running") or (i.get("start_date") or "9999") > d or (i.get("end_date") or "9999") < d:
                continue
            p, k = i.get("params", {}), i["kind"]
            if k == "promo_discount":
                lev["new_joiner_discount"] = max(lev["new_joiner_discount"], min(.3, float(p.get("discount_pct", 10)) / 100 if float(p.get("discount_pct", 10)) > 1 else float(p.get("discount_pct", .1))))
            elif k == "marketing_campaign":
                lev["campaign_boost"] += 1
            elif k == "provider_deal":
                lev["perks"].append("no-gap extras at partner providers")
                lev["service_boost"] += 2
            elif k == "preventive_program":
                lev["perks"].append("free annual health check at our clinic")
            elif k == "retention_program":
                lev["retention"] = True
                lev["perks"].append("loyalty bonus for members of 2+ years")
            elif k == "broker_commission":
                emp = self.top_employers()
                lev["group_employers"], lev["group_discount"] = emp, .05
                lev["perks"].append("5% corporate discount at " + ", ".join(emp[:3]))
            elif k in ("hire", "automation", "training"):
                dept = p.get("dept", "claims")
                if dept in lev["capacity"]:
                    lev["capacity"][dept] += int(p.get("fte", 2) or 2) if k == "hire" else 2
                lev["service_boost"] += 1.5
            elif k == "wellbeing_program":
                lev["service_boost"] += .5
        return lev

    def top_employers(self) -> list[str]:
        cnt: dict[str, int] = {}
        for r in self.co.town.residents():
            e = r.get("employer")
            if e and e != "—" and r["age"] >= 18:
                cnt[e] = cnt.get(e, 0) + 1
        return [e for e, _ in sorted(cnt.items(), key=lambda x: -x[1])[:4]]

    # ------------------------------------------------------------------ prices
    def household_price(self, head: dict[str, Any]) -> float:
        c = head.get("cover") or {}
        if c.get("monthly_price"):
            return float(c["monthly_price"])
        town = self.co.town
        cat = "combined" if c.get("tier") and c.get("extras") else ("hospital" if c.get("tier") else "extras")
        rows = [x for x in town.comparison(head) if x["insurer"] == c.get("insurer") and x["category"] == cat and (x["tier"] == c.get("tier") or cat == "extras")]
        return float(rows[0]["monthly_price"]) if rows else 150.0

    # ------------------------------------------------------------------ one day of accounting
    def step(self, nxt: date) -> DayResult:
        co, st, town = self.co, self.co.store, self.co.town
        day = co.today.isoformat()
        res = town.residents()
        ours = [r for r in res if (r.get("cover") or {}).get("insurer") == "aich"]
        heads: dict[int, dict] = {}
        for r in sorted(ours, key=lambda x: -x["age"]):
            heads.setdefault(r["household"], r)
        ev = st.rows("SELECT * FROM town_events WHERE date=?", (day,))
        data = {e["id"]: json.loads(e["data"] or "{}") for e in ev}
        joins = [e for e in ev if e["kind"] in ("buy", "switch") and e["insurer"] == "aich"]
        leaves = [e for e in ev if e["kind"] == "switch" and data[e["id"]].get("before_insurer") == "aich" and e["insurer"] != "aich"]
        shoppers = {e["resident"] for e in ev if e["kind"] in ("buy", "switch", "keep", "change_plan")}
        enq = [e for e in ev if e["kind"] == "enquiry"]
        leads = len(shoppers | {e["resident"] for e in enq})
        premium_month = sum(self.household_price(h) for h in heads.values())
        premium = premium_month / 30.4
        claims = st.rows("SELECT * FROM town_claims WHERE date=? AND insurer='aich'", (day,))
        exposure = town.health.exposure(day)
        claims_cost = sum(booked(c["insurer_cost"], exposure) for c in claims)
        lev = self.levers()
        n_claims_staff = len(DEPARTMENTS["claims"].agents) + lev["capacity"]["claims"]
        n_care_staff = len(DEPARTMENTS["care"].agents) + lev["capacity"]["care"]
        backlog0 = float(st.get_kv("claims_backlog", 0) or 0)
        arrivals = len([c for c in claims if c["benefit"]])
        cap = n_claims_staff * 2.0
        processed = min(backlog0 + arrivals, cap)
        backlog = backlog0 + arrivals - processed
        st.set_kv("claims_backlog", backlog)
        sla = 100.0 if backlog <= cap else max(50.0, 100.0 * cap / (backlog + arrivals))
        calls = len(enq) + round(len(claims) * .4) + len(joins)
        wait = 35 + 90 * calls / max(1, n_care_staff * 3)
        reviews = st.rows("SELECT stars FROM town_reviews WHERE insurer='aich'")
        stars = [r["stars"] for r in reviews]
        csat = (sum(stars) / len(stars) * 20) if stars else 78.0
        nps = ((sum(1 for s in stars if s == 5) - sum(1 for s in stars if s <= 3)) / len(stars) * 100) if stars else 25.0
        reach = {r["id"] for r in res for c in town.active_campaigns() if town._targets(c["audience"], r)}
        staff_links = {x["resident"] for x in town.employee_contacts()}
        awareness = 100 * len(reach | staff_links | {r["id"] for r in ours}) / max(1, len(res))
        marketing = 12.0 * len(town.active_campaigns()) + 20.0 * lev["campaign_boost"]
        running = [i for i in co.sim.initiatives.values() if i.get("status") in ("approved", "running") and (i.get("start_date") or "9999") <= day <= (i.get("end_date") or "0000")]
        ini_cost = sum(float(i.get("cost_est", 0)) / max(1, (date.fromisoformat(i["end_date"]) - date.fromisoformat(i["start_date"])).days + 1) for i in running
                       if i.get("start_date") and i.get("end_date"))
        opex = premium * .10 + 8.0
        margin = (premium - claims_cost - opex - ini_cost - marketing) / premium if premium else 0.0
        hist = co.store.kpis(28, day)
        prem28 = sum(h["premium_revenue"] for h in hist) + premium
        claim28 = sum(h["claims_incurred"] for h in hist) + claims_cost
        kpi = {"date": day, "policies_in_force": float(len(ours)), "new_sales": len(joins), "cancellations": len(leaves), "net_adds": len(joins) - len(leaves),
               "leads": leads, "conversion": len(joins) / max(1, leads), "premium_revenue": round(premium, 2), "claims_incurred": round(claims_cost, 2),
               "loss_ratio": round(claim28 / prem28, 4) if prem28 else 0.0, "opex": round(opex, 2), "initiative_cost": round(ini_cost, 2), "margin": round(margin, 4),
               "claims_arrivals": arrivals, "claims_processed": round(processed), "claims_backlog": round(backlog), "claims_sla_pct": round(sla, 1),
               "calls": calls, "calls_answered": calls, "avg_wait_s": round(wait, 1), "abandon_pct": round(max(0.0, (wait - 120) / 20), 2), "csat": round(csat, 1),
               "nps": round(nps, 1), "brand_awareness": round(awareness, 1), "marketing_spend": round(marketing, 2), "headcount": float(len(AGENTS)),
               "engagement": 72.0 + min(6, lev["service_boost"]), "utilization_claims": round(min(1.5, (backlog0 + arrivals) / max(cap, 1)), 3),
               "utilization_care": round(min(1.5, calls / max(1, n_care_staff * 3)), 3), "exits": 0}
        st.insert_kpi(kpi)
        channel = lambda rid: ("phone" if any(e["resident"] == rid for e in enq) else "marketing" if rid in reach else "comparison site")  # noqa: E731
        for e in joins:
            r = town.resident(e["resident"]) or {}
            st.db.execute("INSERT INTO daily_sales VALUES (?,?,?,?,?,?)", (day, r.get("suburb", "Wattle Grove"), channel(e["resident"]), e["plan"] or "aich", 1,
                                                                           float(data[e["id"]].get("price", 0)) * 12))
        for e in leaves:
            st.db.execute("INSERT INTO daily_cancellations VALUES (?,?,?,?)", (day, "aich", (data[e["id"]].get("reason") or "switched")[:80], 1))
        for c in claims:
            r = town.resident(c["resident"]) or {}
            st.db.execute("INSERT INTO daily_claims VALUES (?,?,?,?,?)", (day, r.get("suburb", ""), c["kind"], 1, round(booked(c["insurer_cost"], exposure), 2)))
        plans: dict[str, list] = {}
        for r in ours:
            pid = (r.get("cover") or {}).get("plan_id") or f"aich_{(r.get('cover') or {}).get('tier') or 'extras'}"
            plans.setdefault(pid, []).append(r)
        for pid, ms in plans.items():
            st.db.execute("INSERT INTO daily_book VALUES (?,?,?,?)", (day, pid, len(ms), 0.0))
        st.db.execute("INSERT INTO daily_leads VALUES (?,?,?,?,?)", (day, "town", leads, marketing, len(joins) / max(1, leads)))
        for d_, dep in DEPARTMENTS.items():
            st.db.execute("INSERT INTO daily_team VALUES (?,?,?,?,?,?,?,?,?)", (day, d_, float(len(dep.agents)), 0, 0, 0, 0.8, 72.0, 1.0))
        for p in co.sim.products:
            co.sim.s["in_force"][p] = float(sum(len(v) for k, v in plans.items() if k == p))
        co.sim.s["date"] = nxt.isoformat()
        st.commit()
        notes = [f"{len(joins)} joined, {len(leaves)} left, {len(claims)} member claims"] if (joins or leaves or claims) else []
        return DayResult(date=day, kpi=kpi, scheduled=notes)

    def funnel(self, days: int = 28) -> dict[str, Any]:
        """Membership funnel from the agents' own actions."""
        co, st, town = self.co, self.co.store, self.co.town
        since = (co.today - timedelta(days=days)).isoformat()
        ev = st.rows("SELECT * FROM town_events WHERE date>=? AND kind IN ('buy','switch','keep','change_plan','enquiry')", (since,))
        joins = [e for e in ev if e["kind"] in ("buy", "switch") and e["insurer"] == "aich"]
        left = [e for e in ev if e["kind"] == "switch" and json.loads(e["data"] or "{}").get("before_insurer") == "aich" and e["insurer"] != "aich"]
        lost_to: dict[str, int] = {}
        for e in ev:
            if e["kind"] in ("buy", "switch") and e["insurer"] != "aich":
                lost_to[e["insurer"]] = lost_to.get(e["insurer"], 0) + 1
        return {"window_days": days, "residents_reviewing_cover": len({e["resident"] for e in ev if e["kind"] != "enquiry"}),
                "called_us": len([e for e in ev if e["kind"] == "enquiry"]), "joined_us": len(joins), "left_us": len(left),
                "chose_competitors": lost_to, "why_people_joined_us": [e["text"] for e in joins[-5:]], "why_people_left_us": [e["text"] for e in left[-5:]],
                "members_now": sum(1 for r in town.residents() if (r.get("cover") or {}).get("insurer") == "aich"),
                "health_care": town.health.summary("aich", since), "levers_live": self.levers()}
