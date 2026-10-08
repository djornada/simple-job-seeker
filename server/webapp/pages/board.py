"""`/board` — every company you've logged, by latest outreach stage.

Each row expands to the company's full timeline. The log dialog
(`logform.py`) opens from the header and from each row. `?open=<company>`
expands that row (where `POST /add` lands); `?log=<company>` renders the
dialog open, for browsers without JS.
"""
from __future__ import annotations

import sqlite3

import tracker

from ..layout import company_anchor, page, timeline_row
from ..state import db, esc
from .logform import log_button, log_dialog


def _queued(qrow: sqlite3.Row | None) -> str:
    return (f'<p class="meta">queued {qrow["times_queued"]}x · '
            f'last {qrow["last_queued"]}</p>' if qrow else "")


def _row(company: str, events: list[sqlite3.Row], qrow: sqlite3.Row | None,
         is_open: bool) -> str:
    """One company: last date · name · status, expanding to the timeline."""
    last = events[-1]
    lines = "".join(timeline_row(r) for r in events)
    return f"""
<details class="co" id="{company_anchor(company)}"{" open" if is_open else ""}>
  <summary><span class="when">{last["date"]}</span>
    <span class="name">{esc(company)}</span>
    <span class="status">{esc(last["action"])}</span></summary>
  <div class="tl">{_queued(qrow)}{lines}
    <div class="tlactions">{log_button(company, "Log touchpoint")}</div>
  </div>
</details>"""


def page_board(params: dict[str, list[str]]) -> str:
    conn = db()
    rows = conn.execute("SELECT * FROM outreach ORDER BY date, id").fetchall()
    queued = {r["company"]: r for r in conn.execute(
        "SELECT company, last_queued, times_queued FROM queued_companies")}
    want = params.get("open", [""])[0].strip()
    if want:
        want = tracker.resolve_company(conn, want)
    conn.close()

    timelines: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        timelines.setdefault(r["company"], []).append(r)
    n = len(timelines)
    head = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Board</div>
    <h1>{n} compan{"y" if n == 1 else "ies"}</h1>
  </div>
  <div class="buildform">{log_button("", "Log touchpoint", "primary")}</div>
</div>"""
    dialog = log_dialog(params["log"][0].strip() if "log" in params else None)

    notice = ""
    if want and want not in timelines:  # e.g. a company linked from Gaps
        notice = (f'<div class="banner">Nothing logged for {esc(want)} yet. '
                  f'{log_button(want, "Log a touchpoint", "linkbtn")}'
                  f'{_queued(queued.get(want))}</div>')
    if not timelines:
        empty = ('<div class="empty">No outreach logged yet. Work a target, '
                 f'then {log_button("", "log the first touch", "linkbtn")}.</div>')
        return page("Board", "/board", dialog + head + notice + empty)

    by_stage: dict[str, list[str]] = {}
    for company, events in timelines.items():
        by_stage.setdefault(events[-1]["action"], []).append(company)
    sections = []
    for action in sorted(by_stage, key=lambda a: -tracker.STAGE_ORDER.get(a, 0)):
        companies = sorted(by_stage[action],
                           key=lambda c: timelines[c][-1]["date"], reverse=True)
        lines = "".join(_row(c, timelines[c], queued.get(c), c == want)
                        for c in companies)
        sections.append(f'<section class="stage"><h2>{esc(action)} '
                        f'({len(companies)})</h2>{lines}</section>')

    recent = sorted(rows, key=lambda r: r["id"], reverse=True)[:25]
    recent_html = ('<details class="recent"><summary>recent activity</summary>'
                   + "".join(timeline_row(r, link_company=True) for r in recent)
                   + "</details>")
    return page("Board", "/board",
                dialog + head + notice + "".join(sections) + recent_html)
