"""`/due` — follow-ups due or overdue, close them."""
from __future__ import annotations

import datetime as dt
import urllib.parse

from ..layout import page
from ..state import db, esc


def page_due(_: dict[str, list[str]]) -> str:
    conn = db()
    today = dt.date.today().isoformat()
    rows = conn.execute(
        "SELECT id, company, person, action, note, followup_due FROM outreach "
        "WHERE followup_due IS NOT NULL AND followup_done = 0 "
        "AND followup_due <= ? ORDER BY followup_due", (today,)).fetchall()
    conn.close()
    if not rows:
        return page("Due", "/due",
                    '<p class="empty">Nothing due. Go write a post instead.</p>')
    lines = []
    for r in rows:
        overdue = ('<span class="tag-overdue">overdue</span> '
                   if r["followup_due"] < today else "")
        person = f" · {esc(r['person'])}" if r["person"] else ""
        note = f" — {esc(r['note'])}" if r["note"] else ""
        q = urllib.parse.quote(r["company"])
        lines.append(f"""
<div class="rowline">
  <span class="when">{r['followup_due']}</span>
  <span style="flex:1">{overdue}<a href="/company?name={q}">{esc(r['company'])}</a>{person}
    <small style="color:var(--muted)">[last: {esc(r['action'])}]</small>{note}</span>
  <form method="post" action="/done">
    <input type="hidden" name="id" value="{r['id']}">
    <button class="ghost">Close</button>
  </form>
</div>""")
    body = (f'<section class="stage"><h2>follow-ups due</h2>'
            f'{"".join(lines)}</section>')
    return page("Due", "/due", body)
