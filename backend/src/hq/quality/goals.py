"""Weekly goals and reflection: leaders set measurable goals each Monday, the next Monday the results are compared with the goals and the
lessons (what ran that week, what was met or missed) go into the leaders' memories, so strategy is planned and learned from, not just reactive."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

# metric: (how a week is measured, label, higher is better)
METRICS: dict[str, tuple[str, str, bool]] = {
    "new_sales": ("sum", "Memberships sold", True),
    "net_adds": ("sum", "Net new members", True),
    "cancellations": ("sum", "Members lost", False),
    "leads": ("sum", "Leads (residents shopping or calling us)", True),
    "loss_ratio": ("last", "Loss ratio (28-day)", False),
    "claims_sla_pct": ("avg", "Claims within SLA (%)", True),
    "avg_wait_s": ("avg", "Average call wait (s)", False),
    "nps": ("last", "NPS", True),
    "brand_awareness": ("last", "Brand awareness (%)", True),
}


def week_of(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_range(week: str) -> tuple[date, date]:
    y, w = week.split("-W")
    start = date.fromisocalendar(int(y), int(w), 1)
    return start, start + timedelta(days=6)


class Goals:
    def __init__(self, company: Any):
        self.co = company
        company.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS weekly_goals(week TEXT, metric TEXT, target REAL, owner TEXT, why TEXT, set_by TEXT, PRIMARY KEY(week, metric));
        CREATE TABLE IF NOT EXISTS goal_reviews(week TEXT PRIMARY KEY, data TEXT);""")
        company.store.commit()

    # ------------------------------------------------------------------ measuring
    def actual(self, week: str, metric: str, upto: date | None = None) -> float | None:
        a, b = week_range(week)
        if upto:
            b = min(b, upto)
        rows = self.co.store.rows("SELECT * FROM daily_kpi WHERE date>=? AND date<=? ORDER BY date", (a.isoformat(), b.isoformat()))
        if not rows or metric not in rows[0]:
            return None
        how = METRICS[metric][0]
        vals = [float(r[metric] or 0) for r in rows]
        return round(sum(vals), 4) if how == "sum" else round(vals[-1], 4) if how == "last" else round(sum(vals) / len(vals), 4)

    def met(self, metric: str, target: float, actual: float | None) -> bool | None:
        if actual is None:
            return None
        return actual >= target if METRICS[metric][2] else actual <= target

    # ------------------------------------------------------------------ setting
    def set(self, agent: str, goals: list[dict[str, Any]], week: str | None = None) -> dict[str, Any]:
        week = week or week_of(self.co.today)
        ok, bad = [], []
        for g in goals[:6]:
            m = str(g.get("metric", ""))
            try:
                t = float(g.get("target"))
            except (TypeError, ValueError):
                bad.append({"goal": g, "error": "target must be a number"})
                continue
            if m not in METRICS:
                bad.append({"goal": g, "error": f"unknown metric; use one of {sorted(METRICS)}"})
                continue
            self.co.store.db.execute("INSERT OR REPLACE INTO weekly_goals VALUES (?,?,?,?,?,?)",
                                     (week, m, t, str(g.get("owner") or agent), str(g.get("why") or "")[:300], agent))
            ok.append(m)
        self.co.store.commit()
        return {"week": week, "set": ok, "errors": bad}

    def for_week(self, week: str | None = None) -> list[dict[str, Any]]:
        week = week or week_of(self.co.today)
        rows = self.co.store.rows("SELECT * FROM weekly_goals WHERE week=? ORDER BY metric", (week,))
        out = []
        for r in rows:
            act = self.actual(week, r["metric"], self.co.today)
            out.append(r | {"label": METRICS[r["metric"]][1], "higher_is_better": METRICS[r["metric"]][2], "actual_so_far": act,
                            "on_track": self.met(r["metric"], r["target"], act)})
        return out

    def defaults(self, week: str) -> list[dict[str, Any]]:
        """Rule-based goals when nobody set any: 10% better than the last four weeks' weekly average."""
        a, _ = week_range(week)
        rows = self.co.store.rows("SELECT * FROM daily_kpi WHERE date<? ORDER BY date DESC LIMIT 28", (a.isoformat(),))
        if not rows:
            return [{"metric": "new_sales", "target": 2, "why": "First week: start selling"}]
        weeks = max(1.0, len(rows) / 7)
        sales = sum(r["new_sales"] for r in rows) / weeks
        lost = sum(r["cancellations"] for r in rows) / weeks
        return [{"metric": "new_sales", "target": max(1, round(sales * 1.1 + .4)), "why": "Grow sales 10% on the 4-week average"},
                {"metric": "cancellations", "target": max(0, round(lost * .9)), "why": "Keep the members we have"},
                {"metric": "claims_sla_pct", "target": 92, "why": "Service standard"}]

    # ------------------------------------------------------------------ reflecting
    def review(self, week: str) -> dict[str, Any]:
        goals = self.co.store.rows("SELECT * FROM weekly_goals WHERE week=?", (week,))
        a, b = week_range(week)
        items = []
        for g in goals:
            act = self.actual(week, g["metric"])
            items.append({"metric": g["metric"], "label": METRICS[g["metric"]][1], "target": g["target"], "actual": act,
                          "met": self.met(g["metric"], g["target"], act), "owner": g["owner"], "why": g["why"]})
        ran = [i for i in self.co.sim.initiatives.values() if i.get("start_date") and i["start_date"] <= b.isoformat()
               and (i.get("end_date") or "9999") >= a.isoformat() and i.get("status") in ("approved", "running", "completed")]
        camps = self.co.store.rows("SELECT title, by_agent FROM town_campaigns WHERE date>=? AND date<=?", (a.isoformat(), b.isoformat()))
        rev = {"week": week, "from": a.isoformat(), "to": b.isoformat(), "goals": items, "met": sum(1 for i in items if i["met"]),
               "initiatives": [f"{i['id']} {i['title']}" for i in ran], "campaigns": [c["title"] for c in camps]}
        self.co.store.db.execute("INSERT OR REPLACE INTO goal_reviews VALUES (?,?)", (week, json.dumps(rev)))
        self.co.store.commit()
        return rev

    def reviews(self, n: int = 8) -> list[dict[str, Any]]:
        return [json.loads(r["data"]) for r in self.co.store.rows("SELECT data FROM goal_reviews ORDER BY week DESC LIMIT ?", (n,))]

    @staticmethod
    def lesson(rev: dict[str, Any]) -> str:
        parts = [f"{g['label']} target {g['target']:g}, actual {g['actual'] if g['actual'] is not None else 'n/a'} ({'met' if g['met'] else 'missed'})"
                 for g in rev["goals"]]
        tried = ", ".join(rev["initiatives"] + rev["campaigns"]) or "nothing new"
        return f"Week {rev['week']} review: {rev['met']}/{len(rev['goals'])} goals met. " + "; ".join(parts) + f". What we tried: {tried}."
