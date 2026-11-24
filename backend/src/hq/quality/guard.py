"""Guardrail: every document an agent publishes is fact-checked against the company's data.

Numbers the text states about members, sales, losses and the loss ratio are compared with the real values (any reasonable window: today,
7 days, 28 days, all time). Mismatches are flagged on the document, logged, and remembered by the author so they learn to check their tools.
"""
from __future__ import annotations

import json
import re
from typing import Any

NUM = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
# claim: regexes whose first group is the stated number
CLAIMS: dict[str, list[str]] = {
    "members": [NUM + r"\s+(?:members|policies|policyholders)\b", r"(?:members|policies in force)\s+(?:of|is|at|to|=|:)\s*" + NUM + r"\b(?!\s*%)"],
    "sold": [r"(?:sold|signed up|new sales of|acquired)\s+" + NUM + r"\s+(?:new\s+)?(?:memberships|members|policies|sales)",
             NUM + r"\s+(?:new\s+)?(?:memberships|policies)\s+(?:sold|signed)"],
    "loss_ratio_pct": [r"loss ratio\s+(?:of|is|at|was|to|=|:)?\s*" + NUM + r"\s*(?:%|percent)", NUM + r"\s*(?:%|percent)\s+loss ratio"],
}


def truths(co: Any) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {"members": [], "sold": [], "loss_ratio_pct": []}
    last = co.store.kpis(1)
    if last:
        out["members"].append(float(last[-1]["policies_in_force"]))
        out["loss_ratio_pct"].append(100 * float(last[-1]["loss_ratio"]))
    for days in (7, 28):
        k = (co.kpi_window(days) or {}).get("current") or {}
        if "loss_ratio" in k:
            out["loss_ratio_pct"].append(100 * float(k["loss_ratio"]))
    if getattr(co, "economy", None) is not None:
        s = co.sales(0)
        out["members"].append(float(s["members_now"]))
        out["sold"] += [float(v) for v in s["sold"].values()]
    return out


def _texts(x: Any) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [t for k, v in x.items() if k not in ("rows", "columns", "sql", "data") for t in _texts(v)]
    if isinstance(x, list):
        return [t for v in x for t in _texts(v)]
    return []


def _close(v: float, truth: list[float], kind: str) -> bool:
    if kind == "loss_ratio_pct":
        return any(abs(v - t) <= max(2.0, .1 * t) for t in truth)
    return any(abs(v - t) <= max(1.0, .05 * t) for t in truth)


def check(co: Any, content: Any, extra_text: str = "") -> dict[str, Any]:
    text = " ".join(_texts(content) + [extra_text])
    tr = truths(co)
    claims, wrong = [], []
    for kind, pats in CLAIMS.items():
        if not tr[kind]:
            continue
        for p in pats:
            for m in re.finditer(p, text, re.I):
                v = float(m.group(1).replace(",", ""))
                c = {"kind": kind, "claim": m.group(0)[:120], "value": v}
                claims.append(c)
                if not _close(v, tr[kind], kind):
                    wrong.append(c | {"data_says": sorted({round(t, 1) for t in tr[kind]})})
    return {"checked": len(claims), "mismatches": wrong[:10], "ok": not wrong, "truth": {k: sorted({round(t, 1) for t in v}) for k, v in tr.items()}}


class FileGuard:
    def __init__(self, company: Any):
        self.co = company
        company.store.db.execute("CREATE TABLE IF NOT EXISTS file_checks(file TEXT PRIMARY KEY, data TEXT)")
        company.store.commit()
        self.world: Any = None

    def on_create(self, meta: dict[str, Any], content: Any) -> None:
        try:
            res = check(self.co, content, meta.get("summary", ""))
        except Exception as e:  # noqa: BLE001 - a guardrail must never break publishing
            res = {"checked": 0, "mismatches": [], "ok": True, "error": str(e)[:200]}
        self.co.store.db.execute("INSERT OR REPLACE INTO file_checks VALUES (?,?)", (meta["id"], json.dumps(res)))
        self.co.store.commit()
        if not res["ok"] and self.world is not None:
            bad = "; ".join(f"\"{m['claim']}\" (data: {', '.join(map(str, m['data_says']))})" for m in res["mismatches"][:3])
            self.world.log(f"⚠ Fact-check: {meta['id']} {meta['title']} states numbers that don't match the data: {bad}")
            self.world.remember(meta["author"], "lesson", f"My document {meta['id']} '{meta['title']}' had numbers that did not match the data: {bad}. "
                                                          "Check the numbers with my tools before publishing.", .85)

    def get(self, fid: str) -> dict[str, Any] | None:
        r = self.co.store.one("SELECT data FROM file_checks WHERE file=?", (fid,))
        return json.loads(r["data"]) if r else None

    def all(self) -> dict[str, dict[str, Any]]:
        return {r["file"]: json.loads(r["data"]) for r in self.co.store.rows("SELECT * FROM file_checks")}
