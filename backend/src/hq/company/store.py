"""SQLite store for the synthetic company data, with a safe read-only SQL interface for the data agents."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_leads(date TEXT, channel TEXT, leads INTEGER, marketing_spend REAL, conversion REAL);
CREATE TABLE IF NOT EXISTS daily_sales(date TEXT, state TEXT, channel TEXT, product_id TEXT, sales INTEGER, new_premium_pa REAL);
CREATE TABLE IF NOT EXISTS daily_sales_age(date TEXT, product_id TEXT, age_band TEXT, sales INTEGER);
CREATE TABLE IF NOT EXISTS daily_cancellations(date TEXT, product_id TEXT, reason TEXT, cancellations INTEGER);
CREATE TABLE IF NOT EXISTS daily_claims(date TEXT, state TEXT, claim_type TEXT, claims INTEGER, benefits_aud REAL);
CREATE TABLE IF NOT EXISTS daily_book(date TEXT, product_id TEXT, in_force REAL, premium_aud REAL);
CREATE TABLE IF NOT EXISTS daily_team(date TEXT, dept TEXT, headcount REAL, vacancies INTEGER, hires INTEGER, exits INTEGER,
                                      utilization REAL, engagement REAL, productivity REAL);
CREATE TABLE IF NOT EXISTS daily_kpi(
  date TEXT PRIMARY KEY, policies_in_force REAL, new_sales INTEGER, cancellations INTEGER, net_adds INTEGER, leads INTEGER,
  conversion REAL, premium_revenue REAL, claims_incurred REAL, loss_ratio REAL, opex REAL, initiative_cost REAL, margin REAL,
  claims_arrivals INTEGER, claims_processed INTEGER, claims_backlog INTEGER, claims_sla_pct REAL,
  calls INTEGER, calls_answered INTEGER, avg_wait_s REAL, abandon_pct REAL, csat REAL, nps REAL, brand_awareness REAL,
  marketing_spend REAL, headcount REAL, engagement REAL, utilization_claims REAL, utilization_care REAL, exits INTEGER);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, type TEXT, name TEXT, description TEXT,
                                  start_date TEXT, end_date TEXT, effects TEXT);
CREATE TABLE IF NOT EXISTS products(id TEXT PRIMARY KEY, name TEXT, category TEXT, tier TEXT, monthly_price REAL, active INTEGER,
                                    launched TEXT, target TEXT, description TEXT, inclusions TEXT, waiting TEXT);
CREATE TABLE IF NOT EXISTS initiatives(id TEXT PRIMARY KEY, title TEXT, kind TEXT, status TEXT, proposer TEXT, dept TEXT,
                                       cost_est REAL, created TEXT, decided TEXT, start_date TEXT, end_date TEXT, data TEXT);
CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, author TEXT, kind TEXT, title TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY, kind TEXT, title TEXT, dept TEXT, author TEXT, sim_date TEXT, created REAL,
                                 meeting TEXT, summary TEXT, content TEXT);
CREATE TABLE IF NOT EXISTS access_grants(id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, dataset TEXT, granted_by TEXT, reason TEXT,
                                         sim_date TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS access_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, requester TEXT, dataset TEXT, reason TEXT, status TEXT,
                                           reviewer TEXT, note TEXT, sim_date TEXT, created REAL);
CREATE TABLE IF NOT EXISTS room_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, sim_date TEXT, room TEXT, speaker TEXT, kind TEXT, text TEXT, meeting TEXT);
CREATE INDEX IF NOT EXISTS i_roomlog ON room_log(room, id);
CREATE TABLE IF NOT EXISTS convos(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, sim_date TEXT, frm TEXT, to_ TEXT, channel TEXT, text TEXT, room TEXT);
CREATE INDEX IF NOT EXISTS i_convo_f ON convos(frm, id);
CREATE INDEX IF NOT EXISTS i_convo_t ON convos(to_, id);
CREATE TABLE IF NOT EXISTS token_usage(owner TEXT, day TEXT, prompt INTEGER, output INTEGER, calls INTEGER, PRIMARY KEY(owner, day));
CREATE TABLE IF NOT EXISTS agent_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT, ts REAL, sim_date TEXT, kind TEXT, text TEXT, importance REAL);
CREATE INDEX IF NOT EXISTS i_mem ON agent_memory(agent, id);
CREATE TABLE IF NOT EXISTS custom_agents(id TEXT PRIMARY KEY, name TEXT, role TEXT, dept TEXT, hired_by TEXT, reason TEXT, sim_date TEXT);
CREATE INDEX IF NOT EXISTS i_sales ON daily_sales(date);
CREATE INDEX IF NOT EXISTS i_claims ON daily_claims(date);
CREATE INDEX IF NOT EXISTS i_book ON daily_book(date);
CREATE INDEX IF NOT EXISTS i_team ON daily_team(date);
"""

# tables the agents may read with the SQL tool (initiatives/notes/kv are reachable through dedicated tools)
READABLE = {"daily_leads", "daily_sales", "daily_sales_age", "daily_cancellations", "daily_claims", "daily_book", "daily_team",
            "daily_kpi", "events", "products", "initiatives"}
KPI_COLUMNS = ["date", "policies_in_force", "new_sales", "cancellations", "net_adds", "leads", "conversion", "premium_revenue",
               "claims_incurred", "loss_ratio", "opex", "initiative_cost", "margin", "claims_arrivals", "claims_processed",
               "claims_backlog", "claims_sla_pct", "calls", "calls_answered", "avg_wait_s", "abandon_pct", "csat", "nps",
               "brand_awareness", "marketing_spend", "headcount", "engagement", "utilization_claims", "utilization_care", "exits"]


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.db.commit()
        self._ro: sqlite3.Connection | None = None
        self._allowed: set[str] | None = None      # tables the current query may read (None = all READABLE)
        self._denied: set[str] = set()

    # ------------------------------------------------------------------ writes
    def insert_many(self, table: str, rows: Iterable[tuple], cols: int) -> None:
        self.db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * cols)})", rows)

    def insert_kpi(self, row: dict[str, Any]) -> None:
        self.db.execute(f"INSERT OR REPLACE INTO daily_kpi({','.join(KPI_COLUMNS)}) VALUES ({','.join('?' * len(KPI_COLUMNS))})",
                        [row[c] for c in KPI_COLUMNS])

    def commit(self) -> None:
        self.db.commit()

    def reset(self) -> None:
        for t in ("daily_leads", "daily_sales", "daily_sales_age", "daily_cancellations", "daily_claims", "daily_book", "daily_team",
                  "daily_kpi", "events", "products", "initiatives", "notes", "kv", "files", "access_grants", "access_requests"):
            self.db.execute(f"DELETE FROM {t}")
        self.db.commit()

    def set_kv(self, key: str, value: Any) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))
        self.db.commit()

    def get_kv(self, key: str, default: Any = None) -> Any:
        r = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def add_note(self, date: str, author: str, kind: str, title: str, body: str) -> int:
        cur = self.db.execute("INSERT INTO notes(date,author,kind,title,body) VALUES (?,?,?,?,?)", (date, author, kind, title, body))
        self.db.commit()
        return int(cur.lastrowid or 0)

    # ------------------------------------------------------------------ reads
    def rows(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        r = self.db.execute(sql, params).fetchone()
        return dict(r) if r else None

    def last_date(self) -> str | None:
        r = self.db.execute("SELECT MAX(date) FROM daily_kpi").fetchone()
        return r[0] if r and r[0] else None

    def kpis(self, days: int, end: str | None = None) -> list[dict[str, Any]]:
        end = end or self.last_date()
        if not end:
            return []
        return self.rows("SELECT * FROM (SELECT * FROM daily_kpi WHERE date<=? ORDER BY date DESC LIMIT ?) ORDER BY date", (end, days))

    # ------------------------------------------------------------------ safe SQL for agents
    def _readonly(self) -> sqlite3.Connection:
        if self._ro is None:
            self.db.commit()
            ro = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
            ro.row_factory = sqlite3.Row
            ro.execute("PRAGMA query_only=ON")

            def authorizer(action: int, a1: str | None, a2: str | None, dbname: str | None, src: str | None) -> int:
                if action == sqlite3.SQLITE_SELECT or action == sqlite3.SQLITE_FUNCTION:
                    return sqlite3.SQLITE_OK
                if action == sqlite3.SQLITE_READ:
                    if a1 not in READABLE:
                        return sqlite3.SQLITE_DENY
                    if self._allowed is not None and a1 not in self._allowed:   # per-agent data access (Data team grants)
                        self._denied.add(a1)
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK
                return sqlite3.SQLITE_DENY

            ro.set_authorizer(authorizer)
            self._ro = ro
        return self._ro

    def query_readonly(self, sql: str, limit: int = 200, max_steps: int = 3_000_000, allowed: set[str] | None = None) -> dict[str, Any]:
        """Run one SELECT for an agent: read-only connection, whitelisted tables, the agent's data access, row and CPU limits."""
        s = sql.strip().rstrip(";")
        if ";" in s or not s.lower().startswith(("select", "with")):
            return {"error": "only a single SELECT statement is allowed"}
        ro = self._readonly()
        steps = {"n": 0}

        def guard() -> int:
            steps["n"] += 1
            return 1 if steps["n"] > max_steps // 1000 else 0

        ro.set_progress_handler(guard, 1000)
        self._allowed, self._denied = allowed, set()
        try:
            cur = ro.execute(s)
            cols = [d[0] for d in cur.description or []]
            data = cur.fetchmany(limit + 1)
            truncated = len(data) > limit
            return {"columns": cols, "rows": [list(r) for r in data[:limit]], "truncated": truncated}
        except sqlite3.Error as e:
            if self._denied:
                return {"error": f"Access denied to {sorted(self._denied)}. You can read {sorted(allowed or READABLE)}. "
                                 "Ask the Data team for access with request_data_access(dataset, reason).", "denied": sorted(self._denied)}
            return {"error": f"{type(e).__name__}: {e}. Tables you can read: {sorted(allowed if allowed is not None else READABLE)}"}
        finally:
            ro.set_progress_handler(None, 0)
            self._allowed = None

    def close(self) -> None:
        if self._ro:
            self._ro.close()
        self.db.close()
