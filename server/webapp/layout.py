"""Page chrome: the HTML shell (`page`), the outreach `timeline_row`, and
links to a company's Board row (`company_href`)."""
from __future__ import annotations

import datetime as dt
import re
import sqlite3
import urllib.parse

from db import applications as apps_db
from utils import load_config

from .assets import CSS, TABS
from .state import db, esc


def page(title: str, active: str, body: str) -> str:
    conn = db()
    due_n = conn.execute(
        "SELECT COUNT(*) FROM outreach WHERE followup_due IS NOT NULL "
        "AND followup_done = 0 AND followup_due <= ?",
        (dt.date.today().isoformat(),)).fetchone()[0]
    cfg = load_config()  # quiet applications count toward Board's badge
    due_n += len({a["id"] for a in apps_db.stale(conn, cfg)
                  + apps_db.sweep_candidates(conn, cfg)})
    conn.close()
    nav = []
    for href, label in TABS:
        cls = ' class="active"' if href == active else ""
        badge = f'<span class="badge">{due_n}</span>' if href == "/board" and due_n else ""
        nav.append(f'<a href="{href}"{cls}>{label}{badge}</a>')
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/x-icon" href="/favicon.ico">
<title>{esc(title)} · simple-job-seeker</title>
<style>{CSS}</style>
<script src="/static/htmx.min.js"></script>
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
        href = esc(company_href(r["company"]))
        who = f'<a href="{href}">{esc(r["company"])}</a> · '
    else:
        who = ""
    return (f'<div class="rowline"><span class="when">{r["date"]}</span>'
            f'<span style="flex:1">{who}{esc(r["action"])}{person}{note}{fu}'
            f'</span></div>')


def company_anchor(company: str) -> str:
    """The id of a company's row on Board."""
    return "co-" + re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")


def company_href(company: str) -> str:
    """Link to a company's Board row, expanded to its timeline."""
    return (f"/board?open={urllib.parse.quote(company)}"
            f"#{company_anchor(company)}")
