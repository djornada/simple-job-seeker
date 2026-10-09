"""Board's due section: follow-ups due or overdue, applications gone quiet,
and the two-step no-response sweep. Renders nothing when nothing is due."""
from __future__ import annotations

import datetime as dt
import sqlite3

from db import applications as apps_db
from utils import load_config

from ..layout import company_href
from ..state import db, esc


def _app_line(a: sqlite3.Row, max_followups: int) -> str:
    href = esc(company_href(a["company"]))
    return (f'<span class="when">{a["last_activity"]}</span>'
            f'<span style="flex:1"><a href="{href}">'
            f'{esc(a["company"])}</a> · {esc(a["role"])} '
            f'<small style="color:var(--muted)">[{esc(a["status"])}, quiet '
            f'{apps_db.quiet_days(a)}d, follow-ups {a["followups_sent"]}/'
            f'{max_followups}]</small></span>')


def _quiet_groups(stale: list[sqlite3.Row], sweep: list[sqlite3.Row],
                  rules: dict, confirm: bool) -> str:
    """Applications due a follow-up, then the no-response sweep: a list
    with a link that only leads to a confirm step, never moves directly."""
    html = ""
    if stale:
        lines = "".join(f"""
<div class="rowline">{_app_line(a, rules['max_followups'])}
  <form method="post" action="/applications/followup">
    <input type="hidden" name="id" value="{a['id']}">
    <input type="hidden" name="back" value="/board">
    <button class="ghost" title="you followed up by hand">Followed up</button>
  </form>
</div>""" for a in stale)
        html += f'<h3>gone quiet — follow up</h3>{lines}'
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
                    f'<a href="/board">Cancel</a></form>')
        else:
            step = (f'<p class="sweep"><a href="/board?sweep=confirm">Mark '
                    f'{len(sweep)} as no response…</a></p>')
        html += f'<h3>quiet {days}+ days — no response?</h3>{lines}{step}'
    return html


def due_section(params: dict[str, list[str]]) -> str:
    """The top of Board; `?sweep=confirm` shows the sweep's confirm step."""
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
    quiet = _quiet_groups(stale, sweep, apps_db.rules(cfg),
                          params.get("sweep", [""])[0] == "confirm")
    if not rows and not quiet:
        return ""
    lines = []
    for r in rows:
        overdue = ('<span class="tag-overdue">overdue</span> '
                   if r["followup_due"] < today else "")
        person = f" · {esc(r['person'])}" if r["person"] else ""
        note = f" — {esc(r['note'])}" if r["note"] else ""
        href = esc(company_href(r["company"]))
        lines.append(f"""
<div class="rowline">
  <span class="when">{r['followup_due']}</span>
  <span style="flex:1">{overdue}<a href="{href}">{esc(r['company'])}</a>{person}
    <small style="color:var(--muted)">[last: {esc(r['action'])}]</small>{note}</span>
  <form method="post" action="/done">
    <input type="hidden" name="id" value="{r['id']}">
    <button class="ghost">Close</button>
  </form>
</div>""")
    follow = f'<h3>follow-ups</h3>{"".join(lines)}' if lines else ""
    # the same count as the Board tab's badge (`layout.page`)
    n = len(rows) + len({a["id"] for a in stale + sweep})
    return f'<section class="due"><h2>due ({n})</h2>{follow}{quiet}</section>'
