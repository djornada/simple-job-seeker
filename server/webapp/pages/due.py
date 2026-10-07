"""`/due` — follow-ups due or overdue, applications gone quiet, and the
two-step no-response sweep."""
from __future__ import annotations

import datetime as dt
import sqlite3
import urllib.parse

from db import applications as apps_db
from utils import load_config

from ..layout import page
from ..state import db, esc


def _app_line(a: sqlite3.Row, max_followups: int) -> str:
    q = urllib.parse.quote(a["company"])
    return (f'<span class="when">{a["last_activity"]}</span>'
            f'<span style="flex:1"><a href="/company?name={q}">'
            f'{esc(a["company"])}</a> · {esc(a["role"])} '
            f'<small style="color:var(--muted)">[{esc(a["status"])}, quiet '
            f'{apps_db.quiet_days(a)}d, follow-ups {a["followups_sent"]}/'
            f'{max_followups}]</small></span>')


def _quiet_sections(stale: list[sqlite3.Row], sweep: list[sqlite3.Row],
                    rules: dict, confirm: bool) -> str:
    """Applications due a follow-up, then the no-response sweep: a list
    with a button that only leads to a confirm step, never moves directly."""
    html = ""
    if stale:
        lines = "".join(f"""
<div class="rowline">{_app_line(a, rules['max_followups'])}
  <form method="post" action="/applications/followup">
    <input type="hidden" name="id" value="{a['id']}">
    <input type="hidden" name="back" value="/due">
    <button class="ghost" title="you followed up by hand">Followed up</button>
  </form>
</div>""" for a in stale)
        html += (f'<section class="stage"><h2>gone quiet — follow up</h2>'
                 f'{lines}</section>')
    if sweep:
        days = rules["no_response_after_days"]
        lines = "".join(f'<div class="rowline">'
                        f'{_app_line(a, rules["max_followups"])}</div>'
                        for a in sweep)
        if confirm:
            ids = "".join(f'<input type="hidden" name="id" value="{a["id"]}">'
                          for a in sweep)
            step = (f'<form class="sweep" method="post" action="/applications/sweep">'
                    f'{ids}<span>Move these {len(sweep)} to no_response?</span>'
                    f'<button class="primary">Confirm</button> '
                    f'<a href="/due">Cancel</a></form>')
        else:
            step = (f'<p class="sweep"><a href="/due?sweep=confirm">Mark '
                    f'{len(sweep)} as no response…</a></p>')
        html += (f'<section class="stage"><h2>quiet {days}+ days — no '
                 f'response?</h2>{lines}{step}</section>')
    return html


def page_due(params: dict[str, list[str]]) -> str:
    conn = db()
    today = dt.date.today().isoformat()
    rows = conn.execute(
        "SELECT id, company, person, action, note, followup_due FROM outreach "
        "WHERE followup_due IS NOT NULL AND followup_done = 0 "
        "AND followup_due <= ? ORDER BY followup_due", (today,)).fetchall()
    cfg = load_config()
    stale = apps_db.stale(conn, cfg)
    sweep = apps_db.sweep_candidates(conn, cfg)
    conn.close()
    quiet = _quiet_sections(stale, sweep, apps_db.rules(cfg),
                            params.get("sweep", [""])[0] == "confirm")
    if not rows and not quiet:
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
            f'{"".join(lines)}</section>') if lines else ""
    return page("Due", "/due", body + quiet)
