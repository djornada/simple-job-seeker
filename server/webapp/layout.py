"""Page chrome: the HTML shell (`page`) and the outreach `timeline_row`."""
from __future__ import annotations

import datetime as dt
import sqlite3
import urllib.parse

from .assets import CSS, TABS
from .state import db, esc


def page(title: str, active: str, body: str, refresh: bool = False) -> str:
    conn = db()
    due_n = conn.execute(
        "SELECT COUNT(*) FROM outreach WHERE followup_due IS NOT NULL "
        "AND followup_done = 0 AND followup_due <= ?",
        (dt.date.today().isoformat(),)).fetchone()[0]
    conn.close()
    nav = []
    for href, label in TABS:
        cls = ' class="active"' if href == active else ""
        badge = f'<span class="badge">{due_n}</span>' if href == "/due" and due_n else ""
        nav.append(f'<a href="{href}"{cls}>{label}{badge}</a>')
    meta = '<meta http-equiv="refresh" content="3">' if refresh else ""
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
{meta}<title>{esc(title)} · simple-job-seeker</title>
<style>{CSS}</style>
</head><body>
<div class="wrap">
<header class="top">
  <span class="wordmark"><a href="/">queue/</a></span>
  <nav class="tabs">{''.join(nav)}</nav>
</header>
{body}
</div>
</body></html>"""


def timeline_row(r: sqlite3.Row, link_company: bool = False) -> str:
    person = f" · {esc(r['person'])}" if r["person"] else ""
    note = f" — {esc(r['note'])}" if r["note"] else ""
    fu = ""
    if r["followup_due"]:
        state = "" if r["followup_done"] else " pending"
        fu = (f' <small style="color:var(--muted)">'
              f'[follow-up {r["followup_due"]}{state}]</small>')
    if link_company:
        q = urllib.parse.quote(r["company"])
        who = f'<a href="/company?name={q}">{esc(r["company"])}</a> · '
    else:
        who = ""
    return (f'<div class="rowline"><span class="when">{r["date"]}</span>'
            f'<span style="flex:1">{who}{esc(r["action"])}{person}{note}{fu}'
            f'</span></div>')
