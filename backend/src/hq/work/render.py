"""Turn work files into downloads: self-contained HTML (reports, dashboards, slide decks, apps), Markdown, CSV and PowerPoint."""
from __future__ import annotations

import csv
import html
import io
import json
import re
from typing import Any

from hq.agents.roster import AGENTS, DEPARTMENTS

CSS = """body{font-family:system-ui,-apple-system,Segoe UI,sans-serif;margin:0;background:#0b1226;color:#e8ecf6}
main{max-width:1000px;margin:0 auto;padding:32px 24px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:26px 0 8px}
h3{font-size:15px;margin:18px 0 6px}.meta{color:#8a97b4;font-size:13px;margin-bottom:20px}p,li{line-height:1.55}
.card{background:#121a33;border:1px solid #26304a;border-radius:12px;padding:16px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
table{border-collapse:collapse;width:100%;font-size:12.5px}td,th{border-bottom:1px solid #26304a;padding:5px 8px;text-align:left}th{color:#8a97b4}
code{background:#1a2236;padding:1px 5px;border-radius:5px}.sql{color:#6b7896;font-size:11px;font-family:ui-monospace,Menlo,monospace;white-space:pre-wrap}
.kpis{display:flex;gap:12px;flex-wrap:wrap}.kpi{background:#121a33;border:1px solid #26304a;border-radius:10px;padding:10px 14px;min-width:150px}
.kpi small{color:#8a97b4;display:block}.kpi b{font-size:22px}"""

PALETTE = ["#22d3ee", "#f5b942", "#a78bfa", "#2ee6a6", "#ff6b6b", "#60a5fa"]


def esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


def who(agent_id: str) -> str:
    a = AGENTS.get(agent_id)
    return f"{a.name}, {a.role}" if a else agent_id


def dept_name(d: str) -> str:
    return DEPARTMENTS[d].name if d in DEPARTMENTS else d


# ----------------------------------------------------------------------------- markdown (small, safe subset)
def md_to_html(md: str) -> str:
    out, in_ul, in_tbl = [], False, False
    def inline(t: str) -> str:
        t = esc(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        return re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    for line in (md or "").splitlines():
        s = line.rstrip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                continue
            if not in_tbl:
                out.append("<table>")
                in_tbl = True
                out.append("<tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_tbl:
            out.append("</table>")
            in_tbl = False
        m = re.match(r"^\s*[-*•]\s+(.*)", s)
        if m:
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(m.group(1))}</li>")
            continue
        if in_ul:
            out.append("</ul>")
            in_ul = False
        h = re.match(r"^(#{1,4})\s+(.*)", s)
        if h:
            lvl = min(4, len(h.group(1)) + 1)
            out.append(f"<h{lvl}>{inline(h.group(2))}</h{lvl}>")
        elif s:
            out.append(f"<p>{inline(s)}</p>")
    if in_ul:
        out.append("</ul>")
    if in_tbl:
        out.append("</table>")
    return "\n".join(out)


# ----------------------------------------------------------------------------- charts as inline SVG
def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def chart_svg(ch: dict[str, Any], w: int = 460, h: int = 220) -> str:
    cols, rows, typ = ch.get("columns", []), ch.get("rows", []), ch.get("type", "line")
    if typ == "table" or not rows:
        return table_html(cols, rows[:30])
    xi = cols.index(ch["x"]) if ch.get("x") in cols else 0
    ys = [y for y in ch.get("y", []) if y in cols][:4]
    L, R, T, B = 46, 10, 14, 28
    vals = [_num(r[cols.index(y)]) for r in rows for y in ys]
    vals = [v for v in vals if v is not None] or [0]
    lo, hi = min(0, min(vals)) if typ == "bar" else min(vals), max(vals)
    rg = (hi - lo) or 1
    X = lambda i: L + i * (w - L - R) / max(1, len(rows) - 1) if typ != "bar" else L + (i + .5) * (w - L - R) / len(rows)  # noqa: E731
    Y = lambda v: T + (h - T - B) * (1 - (v - lo) / rg)  # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="max-width:{w}px" xmlns="http://www.w3.org/2000/svg" font-family="system-ui" font-size="10">']
    for k in range(5):
        v = lo + rg * k / 4
        parts.append(f'<line x1="{L}" x2="{w-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#26304a"/><text x="{L-4}" y="{Y(v)+3:.1f}" text-anchor="end" fill="#8a97b4">{_fmt(v)}</text>')
    for j, y in enumerate(ys):
        col, yi = PALETTE[j % len(PALETTE)], cols.index(y)
        if typ == "bar":
            bw = (w - L - R) / len(rows) / (len(ys) + .5)
            for i, r in enumerate(rows):
                v = _num(r[yi]) or 0
                x0 = X(i) - bw * len(ys) / 2 + j * bw
                parts.append(f'<rect x="{x0:.1f}" y="{min(Y(v), Y(0)):.1f}" width="{bw*.9:.1f}" height="{abs(Y(0)-Y(v)):.1f}" fill="{col}" rx="2"/>')
        else:
            pts = " ".join(f"{X(i):.1f},{Y(_num(r[yi]) or 0):.1f}" for i, r in enumerate(rows))
            parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2"/>')
        parts.append(f'<rect x="{L+8+j*110}" y="2" width="9" height="9" fill="{col}" rx="2"/><text x="{L+21+j*110}" y="10" fill="#c4cbdb">{esc(y)}</text>')
    step = max(1, len(rows) // 6)
    for i in range(0, len(rows), step):
        parts.append(f'<text x="{X(i):.1f}" y="{h-8}" text-anchor="middle" fill="#8a97b4">{esc(str(rows[i][xi])[-10:])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _fmt(v: float) -> str:
    a = abs(v)
    return f"{v/1e6:.1f}M" if a >= 1e6 else f"{v/1e3:.0f}k" if a >= 1e4 else f"{v:.2f}" if a < 1 and v != 0 else f"{v:.0f}"


def table_html(cols: list[str], rows: list[list[Any]]) -> str:
    return "<table><tr>" + "".join(f"<th>{esc(c)}</th>" for c in cols) + "</tr>" + "".join(
        "<tr>" + "".join(f"<td>{esc(_cell(v))}</td>" for v in r) + "</tr>" for r in rows) + "</table>"


def _cell(v: Any) -> Any:
    return round(v, 4) if isinstance(v, float) else v


def chart_card(ch: dict[str, Any]) -> str:
    return (f'<div class="card"><h3>{esc(ch.get("title"))}</h3>{chart_svg(ch)}'
            + (f'<p>{esc(ch["note"])}</p>' if ch.get("note") else "") + f'<div class="sql">{esc(ch.get("sql",""))}</div></div>')


# ----------------------------------------------------------------------------- pages per kind
def page(f: dict[str, Any], body: str) -> str:
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{esc(f['title'])}</title><style>{CSS}</style></head><body><main><h1>{esc(f['title'])}</h1>"
            f"<div class=meta>{esc(dept_name(f['dept']))} · {esc(who(f['author']))} · company date {esc(f['sim_date'])} · file {esc(f['id'])} · AI Company (synthetic data)</div>"
            f"{body}</main></body></html>")


def to_html(f: dict[str, Any]) -> str:
    c, kind = f.get("content", {}), f["kind"]
    if kind in ("report", "minutes", "brief"):
        return page(f, md_to_html(c.get("markdown", "")) + "".join(chart_card(ch) for ch in c.get("charts", [])))
    if kind == "dashboard":
        kp = "".join(f'<div class="kpi"><small>{esc(k.get("label"))}</small><b>{esc(k.get("value"))}</b></div>' for k in c.get("kpis", []))
        return page(f, f"<p>{esc(c.get('description',''))}</p>" + (f'<div class="kpis">{kp}</div>' if kp else "")
                    + '<div class="grid">' + "".join(chart_card(ch) for ch in c.get("charts", [])) + "</div>")
    if kind == "presentation":
        return deck_html(f)
    if kind == "app":
        return app_html(f)
    return page(f, f"<pre>{esc(json.dumps(c, indent=2))}</pre>")


def deck_html(f: dict[str, Any]) -> str:
    c = f.get("content", {})
    slides = c.get("slides", [])
    secs = []
    for i, s in enumerate(slides):
        ch = chart_svg(s["chart"], 720, 300) if s.get("chart") else ""
        secs.append(f'<section class="s{" on" if i == 0 else ""}"><h2>{esc(s.get("title"))}</h2><ul>'
                    + "".join(f"<li>{esc(b)}</li>" for b in s.get("bullets", [])) + f"</ul>{ch}<div class=n>{i+1} / {len(slides)}</div></section>")
    css = CSS + """section{display:none;min-height:70vh;background:#121a33;border:1px solid #26304a;border-radius:14px;padding:34px 40px;position:relative}
section.on{display:block}section h2{font-size:30px;margin:0 0 18px}section li{font-size:20px;margin:8px 0}.n{position:absolute;right:20px;bottom:14px;color:#8a97b4}
.nav{margin-top:14px;display:flex;gap:10px}button{background:#1a2236;color:#e8ecf6;border:1px solid #26304a;border-radius:8px;padding:8px 16px;cursor:pointer}"""
    js = """let i=0;const S=[...document.querySelectorAll('section')];const go=d=>{S[i].classList.remove('on');i=Math.max(0,Math.min(S.length-1,i+d));S[i].classList.add('on')};
addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key===' ')go(1);if(e.key==='ArrowLeft')go(-1)});"""
    return (f"<!doctype html><html><head><meta charset=utf-8><title>{esc(f['title'])}</title><style>{css}</style></head><body><main>"
            f"<h1>{esc(f['title'])}</h1><div class=meta>Presented by {esc(who(f['author']))} · {esc(c.get('agenda',''))} · company date {esc(f['sim_date'])}</div>"
            + "".join(secs) + "<div class=nav><button onclick='go(-1)'>◀ Previous</button><button onclick='go(1)'>Next ▶</button></div></main>"
            f"<script>{js}</script></body></html>")


def app_html(f: dict[str, Any]) -> str:
    """An IT-built app: the developer's HTML with the data snapshot injected as window.HQ_DATA (no network access needed)."""
    c = f.get("content", {})
    data = json.dumps(c.get("data", {}), default=str).replace("</", "<\\/")
    src = c.get("html", "")
    inject = f"<script>window.HQ_DATA={data};window.HQ_APP={json.dumps({'title': f['title'], 'date': f['sim_date']})};</script>"
    if "<head>" in src:
        return src.replace("<head>", "<head>" + inject, 1)
    return f"<!doctype html><html><head><meta charset=utf-8>{inject}</head><body>{src}</body></html>"


def to_markdown(f: dict[str, Any]) -> str:
    c = f.get("content", {})
    head = f"# {f['title']}\n\n_{dept_name(f['dept'])} · {who(f['author'])} · company date {f['sim_date']} · file {f['id']}_\n\n"
    if f["kind"] == "presentation":
        return head + "\n".join(f"## {i+1}. {s.get('title','')}\n" + "\n".join(f"- {b}" for b in s.get("bullets", [])) + "\n"
                                for i, s in enumerate(c.get("slides", [])))
    body = c.get("markdown") or c.get("description", "")
    charts = "".join(f"\n## {ch['title']}\n\n```sql\n{ch['sql']}\n```\n\n" + _md_table(ch) for ch in c.get("charts", []))
    return head + body + "\n" + charts


def _md_table(ch: dict[str, Any]) -> str:
    cols, rows = ch.get("columns", []), ch.get("rows", [])[:40]
    return "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "".join("| " + " | ".join(str(_cell(v)) for v in r) + " |\n" for r in rows)


def to_csv(f: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    c = f.get("content", {})
    charts = c.get("charts") or [s["chart"] for s in c.get("slides", []) if s.get("chart")]
    for ch in charts:
        w.writerow([f"# {ch.get('title','')}"])
        w.writerow(ch.get("columns", []))
        w.writerows(ch.get("rows", []))
        w.writerow([])
    for name, d in (c.get("data") or {}).items():
        w.writerow([f"# {name}"])
        w.writerow(d.get("columns", []))
        w.writerows(d.get("rows", []))
        w.writerow([])
    return buf.getvalue()


def to_pptx(f: dict[str, Any]) -> bytes | None:
    """A real PowerPoint deck with native charts (needs python-pptx)."""
    try:
        from pptx import Presentation
        from pptx.chart.data import CategoryChartData
        from pptx.dml.color import RGBColor
        from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
        from pptx.util import Inches, Pt
    except ImportError:
        return None
    c = f.get("content", {})
    slides = c.get("slides") or [{"title": ch["title"], "bullets": [ch.get("note", "")], "chart": ch} for ch in c.get("charts", [])] or \
        [{"title": f["title"], "bullets": [ln for ln in (c.get("markdown", "") or "").splitlines() if ln.strip()][:8]}]
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    dark, ink, mute = RGBColor(0x0B, 0x12, 0x26), RGBColor(0xE8, 0xEC, 0xF6), RGBColor(0x8A, 0x97, 0xB4)

    def bg(s: Any) -> None:
        fill = s.background.fill
        fill.solid()
        fill.fore_color.rgb = dark

    def text(s: Any, t: str, x: float, y: float, w: float, h: float, size: int, color: Any, bold: bool = False) -> Any:
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = t
        p.font.size, p.font.bold, p.font.color.rgb = Pt(size), bold, color
        return tf

    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg(s)
    text(s, f["title"], .8, 2.4, 11.5, 1.4, 40, ink, True)
    text(s, f"{who(f['author'])} · {dept_name(f['dept'])} · {f['sim_date']}", .8, 3.9, 11.5, .6, 18, mute)
    if c.get("agenda"):
        text(s, f"Agenda: {c['agenda']}", .8, 4.5, 11.5, 1, 16, mute)
    for sl in slides:
        s = prs.slides.add_slide(prs.slide_layouts[6])
        bg(s)
        text(s, sl.get("title", ""), .6, .4, 12, .9, 30, ink, True)
        ch = sl.get("chart")
        bw = 5.6 if ch else 12
        tf = text(s, "", .6, 1.5, bw, 5.4, 18, ink)
        for j, b in enumerate(sl.get("bullets", [])[:7]):
            p = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            p.text = f"• {b}"
            p.font.size, p.font.color.rgb = Pt(18), ink
            p.space_after = Pt(8)
        if ch and ch.get("rows") and ch.get("type") != "table":
            cols = ch["columns"]
            xi = cols.index(ch["x"]) if ch.get("x") in cols else 0
            cd = CategoryChartData()
            cd.categories = [str(r[xi]) for r in ch["rows"]]
            for y in [y for y in ch.get("y", []) if y in cols][:4]:
                cd.add_series(y, [(_num(r[cols.index(y)]) or 0) for r in ch["rows"]])
            kind = XL_CHART_TYPE.COLUMN_CLUSTERED if ch.get("type") == "bar" else XL_CHART_TYPE.LINE
            gf = s.shapes.add_chart(kind, Inches(6.5), Inches(1.4), Inches(6.3), Inches(5.6), cd)
            chart = gf.chart
            chart.has_legend = True
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
            chart.legend.font.color.rgb = mute
            chart.category_axis.tick_labels.font.color.rgb = mute
            chart.value_axis.tick_labels.font.color.rgb = mute
            chart.category_axis.tick_labels.font.size = chart.value_axis.tick_labels.font.size = Pt(10)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
