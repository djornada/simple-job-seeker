"""`/board` — pipeline overview by latest outreach stage."""
from __future__ import annotations

import urllib.parse

import tracker

from ..layout import page
from ..state import db, esc


def page_board(_: dict[str, list[str]]) -> str:
    conn = db()
    rows = conn.execute(
        "SELECT company, action, date FROM outreach ORDER BY date, id").fetchall()
    conn.close()
    latest = {r["company"]: r for r in rows}
    if not latest:
        return page("Board", "/board",
                    '<p class="empty">No outreach logged yet. Work a target, '
                    'then <a href="/log">log the first touch</a>.</p>')
    by_stage: dict[str, list[tuple[str, str]]] = {}
    for company, r in latest.items():
        by_stage.setdefault(r["action"], []).append((company, r["date"]))
    sections = []
    for action in sorted(by_stage, key=lambda a: -tracker.STAGE_ORDER.get(a, 0)):
        lines = []
        for company, date in sorted(by_stage[action], key=lambda x: x[1],
                                    reverse=True):
            q = urllib.parse.quote(company)
            lines.append(f'<div class="rowline"><span class="when">{date}</span>'
                         f'<a href="/company?name={q}">{esc(company)}</a></div>')
        sections.append(f'<section class="stage"><h2>{esc(action)} '
                        f'({len(lines)})</h2>{"".join(lines)}</section>')
    return page("Board", "/board", "".join(sections))
