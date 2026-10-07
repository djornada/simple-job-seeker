"""`/applications` — every role you applied to, grouped by status."""
from __future__ import annotations

import sqlite3
import urllib.parse

from db import applications as apps_db

from ..layout import page
from ..state import db, esc


def render_app(a: sqlite3.Row, error: str = "") -> str:
    """One application row with its move/follow-up forms. Shared by the
    page and the htmx fragment `POST /applications/move|followup` return."""
    q = urllib.parse.quote(a["company"])
    post = (f' · <a href="{esc(a["url"])}" target="_blank" rel="noopener">'
            'job post</a>' if a["url"] else "")
    meta = (f'<span class="status">{esc(a["status"])}</span> '
            f'<small style="color:var(--muted)">quiet {apps_db.quiet_days(a)}d'
            f' · follow-ups {a["followups_sent"]}</small>')
    err = f' <span class="apperr">{esc(error)}</span>' if error else ""
    hx = ' hx-target="closest .rowline" hx-swap="outerHTML"'
    actions = ""
    moves = apps_db.allowed_moves(a["status"])
    if moves:
        opts = "".join(f'<option value="{m}">{m}</option>' for m in moves)
        actions += f"""
    <form method="post" action="/applications/move" hx-post="/applications/move"{hx}>
      <input type="hidden" name="id" value="{a['id']}">
      <select name="status" aria-label="new status">{opts}</select>
      <input name="note" placeholder="note" aria-label="note">
      <button class="ghost">Move</button>
    </form>
    <form method="post" action="/applications/followup" hx-post="/applications/followup"{hx}>
      <input type="hidden" name="id" value="{a['id']}">
      <button class="ghost" title="you followed up by hand">Followed up</button>
    </form>"""
    return f"""
<div class="rowline app" id="app-{a['id']}">
  <span class="when">{a['applied_on']}</span>
  <span style="flex:1"><a href="/company?name={q}">{esc(a['company'])}</a>
    · {esc(a['role'])}{post} {meta}{err}</span>
  <div class="appactions">{actions}</div>
</div>"""


def page_applications(params: dict[str, list[str]]) -> str:
    conn = db()
    rows = apps_db.list_apps(conn)
    conn.close()
    err = params.get("err", [""])[0]
    banner = f'<p class="banner err">{esc(err)}</p>' if err else ""
    sections = []
    for status in tuple(reversed(apps_db.OPEN)) + apps_db.FINAL:
        group = [a for a in rows if a["status"] == status]
        if group:
            lines = "".join(render_app(a) for a in reversed(group))
            sections.append(f'<section class="stage"><h2>{esc(status)} '
                            f'({len(group)})</h2>{lines}</section>')
    if not sections:
        sections.append('<p class="empty">No applications yet. Hit “I applied” '
                        'on a queue card, or track one below.</p>')
    form = """
<section class="stage"><h2>track an application</h2></section>
<form class="logform" method="post" action="/apply">
  <label>Company <input name="company" required></label>
  <label>Role <input name="role" required></label>
  <label class="full">Job post URL <input name="url" type="url"
         placeholder="optional"></label>
  <label class="full">Note <input name="note" placeholder="optional"></label>
  <div class="full"><button class="primary">I applied</button></div>
</form>"""
    return page("Applications", "/applications",
                banner + "".join(sections) + form)
