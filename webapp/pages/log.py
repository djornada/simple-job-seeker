"""`/log` — log a touchpoint + recent activity."""
from __future__ import annotations

import tracker

from ..layout import page, timeline_row
from ..state import db, esc


def page_log(params: dict[str, list[str]]) -> str:
    conn = db()
    companies = [r[0] for r in conn.execute(
        "SELECT DISTINCT company FROM outreach "
        "UNION SELECT company FROM queued_companies ORDER BY 1")]
    recent = conn.execute(
        "SELECT * FROM outreach ORDER BY id DESC LIMIT 25").fetchall()
    conn.close()
    prefill = params.get("company", [""])[0]
    options = "".join(f'<option value="{esc(c)}">' for c in companies)
    action_opts = "".join(
        f'<option value="{a}"{" selected" if a == "visited" else ""}>{a}</option>'
        for a in tracker.ACTIONS)
    form = f"""
<section class="stage"><h2>log a touchpoint</h2></section>
<form class="logform" method="post" action="/add">
  <label>Company
    <input name="company" list="companies" required autofocus
           value="{esc(prefill)}">
    <datalist id="companies">{options}</datalist>
  </label>
  <label>Person <input name="person" placeholder="who you talked to"></label>
  <label>Action <select name="action">{action_opts}</select></label>
  <label>Follow-up in (days)
    <input name="followup" type="number" min="0" max="365" placeholder="none">
  </label>
  <label class="full">Note
    <input name="note" placeholder="context for future you">
  </label>
  <div class="full"><button class="primary">Log touchpoint</button></div>
</form>"""
    recent_html = ""
    if recent:
        lines = "".join(timeline_row(r, link_company=True) for r in recent)
        recent_html = f'<section class="stage"><h2>recent</h2>{lines}</section>'
    return page("Log", "/log", form + recent_html)
