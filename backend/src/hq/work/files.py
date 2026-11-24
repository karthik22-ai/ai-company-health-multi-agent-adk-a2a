"""Work files and data access: what the teams actually produce, and who may read which data.

* Work files (`files` table): reports, dashboards, presentations, apps and meeting minutes made by the agents. Charts are not
  drawings: each chart carries the SQL it was built from and a snapshot of the real (synthetic) rows it returned.
* Data access (`access_grants` / `access_requests`): every dataset (SQL table) has an owner policy; the Data & Actuarial team
  reviews requests and grants or revokes access. The SQL tool enforces it (biz/store.py authorizer).
* Hires (`custom_agents`): AI agents created by People & Culture survive restarts.
"""
from __future__ import annotations

import json
import time
from typing import Any

from hq.company.store import READABLE, Store

# ----------------------------------------------------------------------------- datasets and the default access policy
DATASETS: dict[str, dict[str, Any]] = {
    "daily_kpi": {"label": "Company KPIs (daily)", "sensitivity": "internal", "default": "all"},
    "products": {"label": "Plans & prices", "sensitivity": "internal", "default": "all"},
    "events": {"label": "Market events", "sensitivity": "internal", "default": "all"},
    "initiatives": {"label": "Initiatives & decisions", "sensitivity": "internal", "default": "all"},
    "daily_sales": {"label": "Sales by state/channel/plan", "sensitivity": "confidential",
                    "default": {"sales", "mkt", "prod", "data", "bi", "exec", "risk"}},
    "daily_sales_age": {"label": "Sales by age band", "sensitivity": "confidential", "default": {"sales", "mkt", "prod", "data", "bi", "exec"}},
    "daily_leads": {"label": "Leads & marketing spend", "sensitivity": "confidential", "default": {"sales", "mkt", "data", "bi", "exec"}},
    "daily_book": {"label": "Policies in force & premium", "sensitivity": "confidential", "default": {"prod", "data", "bi", "exec", "risk", "sales"}},
    "daily_cancellations": {"label": "Cancellations by reason", "sensitivity": "confidential",
                            "default": {"sales", "mkt", "care", "prod", "data", "bi", "exec"}},
    "daily_claims": {"label": "Claims & benefits paid", "sensitivity": "restricted", "default": {"claims", "health", "data", "bi", "exec", "risk"}},
    "daily_team": {"label": "Workforce & HR metrics", "sensitivity": "restricted", "default": {"people", "exec"}},
}
assert set(DATASETS) <= READABLE

KINDS = {"report": "📄", "dashboard": "📊", "presentation": "🎞️", "app": "🧩", "minutes": "📝", "brief": "🗂️"}


class WorkFiles:
    def __init__(self, store: Store, today: Any):
        self.store = store
        self._today = today            # callable -> date (the simulated company date)
        self.on_create: Any = None     # guardrail hook (quality/guard.py): fact-checks every published document

    # ------------------------------------------------------------------ data access
    def allowed_tables(self, agent_id: str) -> set[str]:
        dept = agent_id.split(".")[0]
        out = {t for t, d in DATASETS.items() if d["default"] == "all" or dept in d["default"]}
        for g in self.store.rows("SELECT dataset FROM access_grants WHERE active=1 AND (subject=? OR subject=?)", (agent_id, dept)):
            out.add(g["dataset"])
        return out

    def datasets_for(self, agent_id: str) -> list[dict[str, Any]]:
        allowed = self.allowed_tables(agent_id)
        pend = {r["dataset"] for r in self.store.rows("SELECT dataset FROM access_requests WHERE requester=? AND status='pending'", (agent_id,))}
        return [{"dataset": t, "label": d["label"], "sensitivity": d["sensitivity"],
                 "access": "yes" if t in allowed else ("requested" if t in pend else "no")} for t, d in DATASETS.items()]

    def request_access(self, requester: str, dataset: str, reason: str) -> dict[str, Any]:
        if dataset not in DATASETS:
            return {"error": f"unknown dataset; choose from {sorted(DATASETS)}"}
        if dataset in self.allowed_tables(requester):
            return {"ok": True, "note": "you already have access"}
        if self.store.one("SELECT id FROM access_requests WHERE requester=? AND dataset=? AND status='pending'", (requester, dataset)):
            return {"ok": True, "note": "already requested, waiting for the Data team"}
        cur = self.store.db.execute("INSERT INTO access_requests(requester,dataset,reason,status,sim_date,created) VALUES (?,?,?,?,?,?)",
                                    (requester, dataset, reason[:300], "pending", self._today().isoformat(), time.time()))
        self.store.commit()
        return {"ok": True, "request_id": int(cur.lastrowid or 0), "status": "pending"}

    def access_requests(self, status: str | None = "pending") -> list[dict[str, Any]]:
        q = "SELECT * FROM access_requests" + (" WHERE status=?" if status else "") + " ORDER BY id DESC LIMIT 50"
        rows = self.store.rows(q, (status,) if status else ())
        for r in rows:
            r["dataset_label"] = DATASETS.get(r["dataset"], {}).get("label", r["dataset"])
            r["sensitivity"] = DATASETS.get(r["dataset"], {}).get("sensitivity")
        return rows

    def review_access(self, request_id: int, reviewer: str, approve: bool, note: str) -> dict[str, Any]:
        r = self.store.one("SELECT * FROM access_requests WHERE id=?", (int(request_id),))
        if not r:
            return {"error": "no such request"}
        if r["status"] != "pending":
            return {"error": f"request already {r['status']}"}
        self.store.db.execute("UPDATE access_requests SET status=?, reviewer=?, note=? WHERE id=?",
                              ("approved" if approve else "rejected", reviewer, note[:300], int(request_id)))
        if approve:
            self.store.db.execute("INSERT INTO access_grants(subject,dataset,granted_by,reason,sim_date) VALUES (?,?,?,?,?)",
                                  (r["requester"], r["dataset"], reviewer, r["reason"], self._today().isoformat()))
        self.store.commit()
        return {"ok": True, "request_id": int(request_id), "status": "approved" if approve else "rejected", "requester": r["requester"],
                "dataset": r["dataset"]}

    def grants(self) -> list[dict[str, Any]]:
        rows = self.store.rows("SELECT * FROM access_grants WHERE active=1 ORDER BY id DESC")
        for r in rows:
            r["dataset_label"] = DATASETS.get(r["dataset"], {}).get("label", r["dataset"])
        return rows

    def revoke(self, grant_id: int, by: str, reason: str) -> dict[str, Any]:
        g = self.store.one("SELECT * FROM access_grants WHERE id=? AND active=1", (int(grant_id),))
        if not g:
            return {"error": "no such active grant"}
        self.store.db.execute("UPDATE access_grants SET active=0, reason=? WHERE id=?", (f"revoked by {by}: {reason}"[:300], int(grant_id)))
        self.store.commit()
        return {"ok": True, "revoked": int(grant_id), "subject": g["subject"], "dataset": g["dataset"]}

    def access_matrix(self) -> dict[str, Any]:
        """Default policy plus grants, for the Data team's board and the UI."""
        return {"datasets": [{"dataset": t, **{k: (sorted(v) if isinstance(v, set) else v) for k, v in d.items()}} for t, d in DATASETS.items()],
                "grants": self.grants(), "pending": self.access_requests("pending")}

    # ------------------------------------------------------------------ charts from real data
    def run_charts(self, agent_id: str, charts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        """Execute every chart's SQL with the author's data access. Returns (charts with data, errors)."""
        out, errors = [], []
        allowed = self.allowed_tables(agent_id)
        for i, ch in enumerate(charts[:8]):
            if not isinstance(ch, dict) or not ch.get("sql"):
                errors.append(f"chart {i+1}: needs title, type and sql")
                continue
            res = self.store.query_readonly(str(ch["sql"]), limit=400, allowed=allowed)
            if "error" in res:
                errors.append(f"chart {i+1} ({ch.get('title','')}): {res['error']}")
                continue
            cols = res["columns"]
            x = ch.get("x") or (cols[0] if cols else "")
            ys = ch.get("y") or [c for c in cols if c != x][:3]
            ys = [ys] if isinstance(ys, str) else list(ys)
            bad = [c for c in [x, *ys] if c not in cols]
            if bad and ch.get("type", "line") != "table":
                errors.append(f"chart {i+1}: columns {bad} are not in the result {cols}")
                continue
            rows = res["rows"]
            if rows and ch.get("type", "line") in ("line", "area") and cols and isinstance(rows[0][cols.index(x)], str) and rows[0][cols.index(x)] > rows[-1][cols.index(x)]:
                rows = rows[::-1]                               # time series oldest -> newest
            out.append({"title": str(ch.get("title") or f"Chart {i+1}")[:80], "type": ch.get("type", "line"), "sql": ch["sql"], "x": x, "y": ys,
                        "columns": cols, "rows": rows, "note": str(ch.get("note", ""))[:200]})
        return out, errors

    # ------------------------------------------------------------------ files
    def _next_id(self, kind: str) -> str:
        n = (self.store.one("SELECT COUNT(*) AS n FROM files") or {"n": 0})["n"] + 1
        return f"{kind[:1].upper()}{n:04d}"

    def create(self, kind: str, title: str, author: str, content: dict[str, Any], *, summary: str = "", meeting: str | None = None) -> dict[str, Any]:
        fid = self._next_id(kind)
        row = {"id": fid, "kind": kind, "title": title[:120], "dept": author.split(".")[0], "author": author, "sim_date": self._today().isoformat(),
               "created": time.time(), "meeting": meeting, "summary": summary[:400], "content": json.dumps(content, default=str)}
        self.store.db.execute("INSERT INTO files VALUES (:id,:kind,:title,:dept,:author,:sim_date,:created,:meeting,:summary,:content)", row)
        self.store.commit()
        meta = self.meta(row)
        if self.on_create:
            self.on_create(meta, content)
        return meta

    @staticmethod
    def meta(row: dict[str, Any]) -> dict[str, Any]:
        return {k: row[k] for k in ("id", "kind", "title", "dept", "author", "sim_date", "created", "meeting", "summary")} | {"icon": KINDS.get(row["kind"], "📄")}

    def get(self, fid: str) -> dict[str, Any] | None:
        r = self.store.one("SELECT * FROM files WHERE id=?", (fid,))
        if not r:
            return None
        return self.meta(r) | {"content": json.loads(r["content"] or "{}")}

    def list(self, *, dept: str | None = None, author: str | None = None, kind: str | None = None, meeting: str | None = None,
             limit: int = 100) -> list[dict[str, Any]]:
        q, p = "SELECT * FROM files WHERE 1=1", []
        for col, v in (("dept", dept), ("author", author), ("kind", kind), ("meeting", meeting)):
            if v:
                q += f" AND {col}=?"
                p.append(v)
        q += " ORDER BY created DESC LIMIT ?"
        p.append(int(limit))
        return [self.meta(r) for r in self.store.rows(q, tuple(p))]

    def counts(self) -> dict[str, int]:
        return {r["kind"]: r["n"] for r in self.store.rows("SELECT kind, COUNT(*) AS n FROM files GROUP BY kind")}

    # ------------------------------------------------------------------ hires
    def save_hire(self, spec: Any, hired_by: str, reason: str) -> None:
        self.store.db.execute("INSERT OR REPLACE INTO custom_agents VALUES (?,?,?,?,?,?,?)",
                              (spec.id, spec.name, spec.role, spec.dept, hired_by, reason[:300], self._today().isoformat()))
        self.store.commit()

    def hires(self) -> list[dict[str, Any]]:
        return self.store.rows("SELECT * FROM custom_agents ORDER BY sim_date")
