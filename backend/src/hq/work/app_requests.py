"""IT's app backlog: what the business needs built, and why.

Requests come from three places:
  agent   any employee files one with the request_app tool when their work needs a tool that doesn't exist
  signal  the company's own numbers: membership milestones and metrics that stay off target raise a request automatically
  ceo     you, through "ask a department" (work_request to IT)

Every week the Head of IT ranks the open backlog by impact; a developer builds the top item with create_app(request_id=...),
the request is closed with the app's file id, and the team that asked is told (and remembers it).
"""
from __future__ import annotations

import time
from typing import Any

from hq.agents.roster import AGENTS, dept_lead

STATUSES = ("open", "planned", "building", "done", "declined")
MILESTONES = [25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]

# signal id -> (dept that needs it, title, use case, suggested data)
SIGNALS: dict[str, tuple[str, str, str, dict[str, str]]] = {
    "growth": ("sales", "Membership growth tracker",
               "We just passed {value} policies in force. Sales and leadership need one place to watch growth: policies, new sales, "
               "cancellations and net adds by day, with the trend, so we can see what is driving it and plan capacity before the next milestone.",
               {"growth": "SELECT date, policies_in_force, new_sales, cancellations, net_adds FROM daily_kpi ORDER BY date DESC LIMIT 90"}),
    "claims_sla": ("claims", "Claims SLA recovery board",
                   "Claims within SLA has averaged {value}% over the last week, below the 90% standard. Claims needs to see arrivals vs processed "
                   "and the backlog each day to staff up and clear it.",
                   {"claims": "SELECT date, claims_arrivals, claims_processed, claims_backlog, claims_sla_pct FROM daily_kpi ORDER BY date DESC LIMIT 60"}),
    "wait": ("care", "Contact centre wait monitor",
             "Average call wait has been {value}s over the last week, above our 60s target. Member Care needs calls, answered, wait and "
             "abandon rate by day to fix rostering.",
             {"calls": "SELECT date, calls, calls_answered, avg_wait_s, abandon_pct, csat FROM daily_kpi ORDER BY date DESC LIMIT 60"}),
    "cancellations": ("care", "Cancellation early-warning app",
                      "We lost {value} members in the last week. Retention needs cancellations next to new sales, NPS and CSAT by day to spot "
                      "the pattern early and call at-risk members.",
                      {"churn": "SELECT date, new_sales, cancellations, net_adds, nps, csat FROM daily_kpi ORDER BY date DESC LIMIT 90"}),
    "loss_ratio": ("data", "Loss ratio watch",
                   "The loss ratio has averaged {value}% over the last week, above our 80% ceiling. Actuarial and Product need premium vs claims "
                   "by day to find what is driving it before the next price review.",
                   {"claims_cost": "SELECT date, premium_revenue, claims_incurred, loss_ratio FROM daily_kpi ORDER BY date DESC LIMIT 90"}),
}


class AppRequests:
    def __init__(self, company: Any):
        self.co = company
        self.store = company.store
        self.store.db.executescript("""
        CREATE TABLE IF NOT EXISTS app_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, sim_date TEXT, requester TEXT, dept TEXT, title TEXT,
            use_case TEXT, data_needed TEXT, impact TEXT, source TEXT, status TEXT, priority INTEGER, file_id TEXT, note TEXT, updated REAL);""")
        self.store.commit()

    # ------------------------------------------------------------------ requests
    def add(self, requester: str, title: str, use_case: str, data_needed: str = "", impact: str = "", source: str = "agent") -> dict[str, Any]:
        title, use_case = title.strip()[:90], use_case.strip()
        if len(title) < 4 or len(use_case) < 20:
            return {"error": "give the app a title and describe the use case (who uses it, for what decision)"}
        dup = self.find_open(title)
        if dup:
            return {"ok": True, "request_id": dup["id"], "status": dup["status"], "note": "IT already has this on the backlog"}
        dept = AGENTS[requester].dept if requester in AGENTS else "exec"
        cur = self.store.db.execute(
            "INSERT INTO app_requests(sim_date,requester,dept,title,use_case,data_needed,impact,source,status,priority,file_id,note,updated) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.co.today.isoformat(), requester, dept, title, use_case[:1200], data_needed[:1500], impact[:400], source, "open", 0, None, "", time.time()))
        self.store.commit()
        return {"ok": True, "request_id": cur.lastrowid, "status": "open"}

    def find_open(self, title: str) -> dict[str, Any] | None:
        t = title.strip().lower()
        for r in self.list(("open", "planned", "building")):
            if r["title"].lower() == t:
                return r
        return None

    def get(self, rid: int) -> dict[str, Any] | None:
        rows = self.store.rows("SELECT * FROM app_requests WHERE id=?", (int(rid),))
        return rows[0] if rows else None

    def list(self, statuses: tuple[str, ...] | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if statuses:
            q = f"SELECT * FROM app_requests WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY priority DESC, id LIMIT ?"
            return self.store.rows(q, (*statuses, limit))
        return self.store.rows("SELECT * FROM app_requests ORDER BY id DESC LIMIT ?", (limit,))

    def update(self, rid: int, **fields: Any) -> None:
        fields["updated"] = time.time()
        sets = ",".join(f"{k}=?" for k in fields)
        self.store.db.execute(f"UPDATE app_requests SET {sets} WHERE id=?", (*fields.values(), int(rid)))
        self.store.commit()

    def prioritise(self, by: str, ranking: list[dict[str, Any]]) -> dict[str, Any]:
        """ranking: [{"id": 3, "decision": "build|later|decline", "note": "why"}, ...] in priority order (first = most important)."""
        done, errors = [], []
        n = len(ranking)
        for i, item in enumerate(ranking):
            try:
                rid = int(item.get("id"))
            except (TypeError, ValueError):
                errors.append(f"bad id in {item}")
                continue
            r = self.get(rid)
            if not r or r["status"] not in ("open", "planned"):
                errors.append(f"request {rid} is not open")
                continue
            decision = str(item.get("decision", "build")).lower()
            status = {"build": "planned", "later": "open", "decline": "declined"}.get(decision)
            if not status:
                errors.append(f"request {rid}: decision must be build, later or decline")
                continue
            note = str(item.get("note", ""))[:300]
            self.update(rid, status=status, priority=n - i, note=f"{note} ({by})" if note else by)
            done.append({"id": rid, "status": status})
        return {"ok": bool(done), "updated": done, "errors": errors}

    def next_to_build(self) -> dict[str, Any] | None:
        for statuses in (("planned",), ("open",)):
            rows = self.list(statuses, 1)
            if rows:
                return rows[0]
        return None

    def complete(self, rid: int, file_id: str) -> dict[str, Any] | None:
        r = self.get(rid)
        if not r or r["status"] in ("done", "declined"):
            return None
        self.update(rid, status="done", file_id=file_id)
        return self.get(rid)

    def counts(self) -> dict[str, int]:
        return {r["status"]: r["n"] for r in self.store.rows("SELECT status, COUNT(*) AS n FROM app_requests GROUP BY status")}

    # ------------------------------------------------------------------ the company's own numbers raise requests
    def scan_signals(self) -> list[dict[str, Any]]:
        """Growth milestones and metrics off target for a week become app requests (each signal at most once while it stays open)."""
        k = self.store.kpis(7)
        if not k:
            return []
        last = k[-1]
        avg = lambda c: sum(float(r.get(c) or 0) for r in k) / len(k)   # noqa: E731
        hits: list[tuple[str, Any]] = []
        pif = float(last.get("policies_in_force") or 0)
        reached = max([m for m in MILESTONES if pif >= m], default=0)
        if reached and reached > int(self.store.get_kv("app_signal_milestone", 0) or 0):
            self.store.set_kv("app_signal_milestone", reached)
            hits.append(("growth", f"{reached:,}"))
        if len(k) >= 5:
            if avg("claims_sla_pct") < 90:
                hits.append(("claims_sla", f"{avg('claims_sla_pct'):.0f}"))
            if avg("avg_wait_s") > 60:
                hits.append(("wait", f"{avg('avg_wait_s'):.0f}"))
            lost = sum(float(r.get("cancellations") or 0) for r in k)
            if lost >= max(2, 0.01 * pif):
                hits.append(("cancellations", f"{lost:,.0f}"))
            if avg("loss_ratio") > 0.8:
                hits.append(("loss_ratio", f"{avg('loss_ratio') * 100:.0f}"))
        raised = []
        for sig, value in hits:
            dept, title, use, data = SIGNALS[sig]
            if self.find_open(title):
                continue
            import json
            res = self.add(dept_lead(dept).id, title, use.format(value=value), json.dumps(data), f"signal: {sig}", source="signal")
            if res.get("request_id"):
                raised.append({"id": res["request_id"], "signal": sig, "title": title, "dept": dept})
        return raised
