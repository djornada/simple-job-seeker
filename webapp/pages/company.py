"""`/company` — full outreach timeline for one company."""
from __future__ import annotations

import tracker

from ..layout import page, timeline_row
from ..state import db, esc


def page_company(params: dict[str, list[str]]) -> str:
    name = params.get("name", [""])[0].strip()
    if not name:
        return page("Company", "/board",
                    '<p class="empty">No company given. Pick one on the '
                    '<a href="/board">board</a>.</p>')
    conn = db()
    company = tracker.resolve_company(conn, name)
    rows = conn.execute(
        "SELECT date, action, person, note, followup_due, followup_done "
        "FROM outreach WHERE company = ? ORDER BY date, id", (company,)).fetchall()
    qrow = conn.execute(
        "SELECT last_queued, times_queued FROM queued_companies WHERE company = ?",
        (company,)).fetchone()
    conn.close()
    queued = (f'<p class="meta">queued {qrow["times_queued"]}x · '
              f'last {qrow["last_queued"]}</p>' if qrow else "")
    head = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Company</div>
    <h1>{esc(company)}</h1>
    {queued}
  </div>
  <form class="buildform" method="get" action="/log">
    <input type="hidden" name="company" value="{esc(company)}">
    <button class="ghost">Log touchpoint</button>
  </form>
</div>"""
    if rows:
        lines = "".join(timeline_row(r) for r in rows)
        body = f'<section class="stage"><h2>timeline</h2>{lines}</section>'
    else:
        body = '<p class="empty">No outreach history yet.</p>'
    return page(company, "/board", head + body)
