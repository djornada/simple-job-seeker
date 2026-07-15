#!/usr/bin/env python3
"""
Local web UI for the daily queue + outreach tracker.

Same principle as the CLIs: nothing touches LinkedIn programmatically.
The app renders links; the click is human.

Pure stdlib (http.server + sqlite3). Binds 127.0.0.1 by default —
state.db holds data about real people, do not expose it.

Usage:
    python webapp.py           # serve on http://127.0.0.1:8765

Pages:
    /            daily queue: check off targets, draft notes, rebuild
    /board       pipeline overview by latest stage
    /due         follow-ups due or overdue, close them
    /log         log a touchpoint + recent activity
    /company     full timeline for one company
"""

from __future__ import annotations

import datetime as dt
import html
import re
import sqlite3
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import queue_agent as qa
import tracker

# --------------------------------------------------------------------------- #
# Shared state (background workers keep requests snappy)
# --------------------------------------------------------------------------- #

BUILD = {"running": False, "error": ""}
BUILD_LOCK = threading.Lock()
NOTES_PENDING: set[str] = set()          # queue item uids with a note in flight
NOTES_LOCK = threading.Lock()

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(qa.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


# --------------------------------------------------------------------------- #
# Background workers
# --------------------------------------------------------------------------- #

def build_worker(with_notes: bool) -> None:
    try:
        cfg = qa.load_config()
        conn = qa.db_connect()
        limit = cfg["targets"].get("per_day", 10)
        cooldown = cfg["targets"].get("company_cooldown_days", 30)
        queue = qa.select_queue(conn, qa.collect_jobs(cfg), cfg, limit, cooldown)
        notes: dict[str, str] = {}
        if with_notes:
            for j in queue:
                note = qa.draft_note(j, cfg)
                if note:
                    notes[j.uid] = note
        if queue:
            qa.save_queue(conn, queue, notes)
            links = {j.uid: qa.build_links(j, cfg) for j in queue}
            qa.OUT_DIR.mkdir(exist_ok=True)
            out_file = qa.OUT_DIR / f"{dt.date.today().isoformat()}.md"
            out_file.write_text(qa.render(queue, links, notes))
        conn.close()
        error = ""
    except Exception as e:  # noqa: BLE001 — surface any failure in the UI
        error = str(e) or e.__class__.__name__
    with BUILD_LOCK:
        BUILD["running"] = False
        BUILD["error"] = error


def note_worker(date: str, uid: str) -> None:
    try:
        cfg = qa.load_config()
        conn = db()
        row = conn.execute(
            "SELECT source, title, company, url, location FROM queue_items "
            "WHERE date = ? AND uid = ?", (date, uid)).fetchone()
        if row:
            job = qa.Job(source=row["source"], title=row["title"],
                         company=row["company"], url=row["url"],
                         location=row["location"])
            note = qa.draft_note(job, cfg)
            if note:
                conn.execute(
                    "UPDATE queue_items SET note = ? WHERE date = ? AND uid = ?",
                    (note, date, uid))
                conn.commit()
        conn.close()
    finally:
        with NOTES_LOCK:
            NOTES_PENDING.discard(uid)


# --------------------------------------------------------------------------- #
# Page shell
# --------------------------------------------------------------------------- #

CSS = """
:root {
  --paper: #EDF1EE; --card: #FFFFFF; --ink: #17251F; --muted: #5A6962;
  --line: #D6DED8; --accent: #0E6B5C; --accent-ink: #0A5246;
  --amber: #9A5B12; --amber-bg: #F5E8D4;
  --mono: ui-monospace, "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--accent-ink); text-underline-offset: 2px; }
a:hover { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 880px; margin: 0 auto; padding: 0 20px 64px; }
header.top { display: flex; align-items: baseline; gap: 24px;
  padding: 18px 0 14px; border-bottom: 1px solid var(--line); }
.wordmark { font-family: var(--mono); font-weight: 700; letter-spacing: -0.5px; }
.wordmark a { color: var(--ink); text-decoration: none; }
nav.tabs { display: flex; gap: 18px; font-size: 14px; }
nav.tabs a { text-decoration: none; color: var(--muted); padding: 2px 0; }
nav.tabs a:hover { color: var(--ink); }
nav.tabs a.active { color: var(--ink); box-shadow: 0 2px 0 var(--accent); }
.badge { font-family: var(--mono); font-size: 11px; background: var(--amber-bg);
  color: var(--amber); border-radius: 8px; padding: 0 6px; margin-left: 4px; }
.manifest { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 24px; margin: 28px 0 8px; flex-wrap: wrap; }
.eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: .14em;
  color: var(--muted); text-transform: uppercase; }
.manifest h1 { font-size: 32px; letter-spacing: -0.02em; margin: 2px 0 0;
  font-weight: 750; font-family: var(--mono); }
.progress { display: flex; align-items: center; gap: 10px; padding-bottom: 8px; }
.segs { display: flex; gap: 3px; flex-wrap: wrap; max-width: 280px; }
.seg { width: 14px; height: 14px; border-radius: 3px;
  border: 1px solid var(--line); background: var(--card); }
.seg.on { background: var(--accent); border-color: var(--accent); }
.progress .count { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.buildform { display: flex; align-items: center; gap: 12px; padding-bottom: 6px; }
button.primary { background: var(--accent); color: #fff; border: 0;
  border-radius: 6px; padding: 8px 14px; font: 600 14px system-ui; cursor: pointer; }
button.primary:hover { background: var(--accent-ink); }
button.primary[disabled] { opacity: .5; cursor: default; }
label.opt { font-size: 13px; color: var(--muted); display: flex; gap: 5px;
  align-items: center; }
.banner { margin: 16px 0; padding: 10px 14px; border: 1px solid var(--line);
  border-left: 3px solid var(--accent); background: var(--card);
  border-radius: 6px; font-size: 14px; }
.banner.err { border-left-color: #8C2F1B; }
nav.dates { font-family: var(--mono); font-size: 12px; display: flex; gap: 12px;
  margin: 10px 0 18px; flex-wrap: wrap; }
nav.dates a { color: var(--muted); }
nav.dates a.cur { color: var(--ink); font-weight: 700; text-decoration: none; }
article.target { display: flex; gap: 14px; background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px;
  margin-bottom: 10px; }
article.target.done { opacity: .55; }
article.target.done h2 { text-decoration: line-through; }
.tick { width: 26px; height: 26px; border-radius: 6px;
  border: 1.5px solid var(--line); background: var(--paper); cursor: pointer;
  color: var(--accent); font-size: 15px; line-height: 1; }
.tick:hover { border-color: var(--accent); }
article.target h2 { font-size: 16px; margin: 0; display: flex; gap: 8px;
  align-items: baseline; }
.score { font-family: var(--mono); font-size: 11px; font-weight: 400;
  color: var(--muted); border: 1px solid var(--line); padding: 0 5px;
  border-radius: 8px; }
p.meta { margin: 2px 0 6px; color: var(--muted); font-size: 13px; }
p.linkrow { margin: 0; font-size: 13px; display: flex; gap: 14px; flex-wrap: wrap; }
p.note { margin: 8px 0 0; font-size: 13.5px; background: var(--paper);
  border-radius: 6px; padding: 8px 10px; }
p.note .len { font-family: var(--mono); font-size: 11px; color: var(--muted);
  margin-left: 6px; }
p.note.pending { color: var(--muted); font-style: italic; }
button.ghost { background: none; border: 1px solid var(--line);
  border-radius: 6px; padding: 4px 10px; font-size: 12.5px;
  color: var(--accent-ink); cursor: pointer; }
button.ghost:hover { border-color: var(--accent); }
section.stage { margin: 26px 0; }
section.stage h2 { font-family: var(--mono); font-size: 12px;
  letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding-bottom: 6px; margin: 0 0 4px; }
.rowline { display: flex; gap: 14px; padding: 7px 2px; align-items: baseline;
  border-bottom: 1px solid var(--line); font-size: 14px; }
.rowline .when { font-family: var(--mono); font-size: 12px; color: var(--muted);
  min-width: 88px; }
.tag-overdue { font-family: var(--mono); font-size: 11px; color: var(--amber);
  background: var(--amber-bg); padding: 0 6px; border-radius: 8px; }
form.logform { background: var(--card); border: 1px solid var(--line);
  border-radius: 8px; padding: 16px; display: grid;
  grid-template-columns: 1fr 1fr; gap: 12px; margin: 8px 0 20px; }
form.logform label { font-size: 12.5px; color: var(--muted); display: flex;
  flex-direction: column; gap: 4px; }
input, select { font: 14px system-ui; padding: 7px 9px;
  border: 1px solid var(--line); border-radius: 6px; background: var(--paper);
  color: var(--ink); }
.full { grid-column: 1 / -1; }
.empty { margin: 40px 0; color: var(--muted); }
.hint { margin-top: 24px; color: var(--muted); font-size: 13px; }
@media (max-width: 620px) {
  form.logform { grid-template-columns: 1fr; }
  .manifest { flex-direction: column; align-items: flex-start; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

TABS = [("/", "Queue"), ("/board", "Board"), ("/due", "Due"), ("/log", "Log")]


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
<link rel="icon" href="data:,">
{meta}<title>{esc(title)} · linkedin-queue</title>
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


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

def page_queue(params: dict[str, list[str]]) -> str:
    conn = db()
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM queue_items ORDER BY date DESC LIMIT 10")]
    today = dt.date.today().isoformat()
    date = params.get("date", [""])[0]
    if not DATE_RE.fullmatch(date):
        date = dates[0] if dates else today
    rows = conn.execute(
        "SELECT * FROM queue_items WHERE date = ? ORDER BY score DESC, company",
        (date,)).fetchall()
    conn.close()

    cfg = qa.load_config()
    with BUILD_LOCK:
        building, error = BUILD["running"], BUILD["error"]
    with NOTES_LOCK:
        pending = set(NOTES_PENDING)

    done_n = sum(r["done"] for r in rows)
    weekday = dt.date.fromisoformat(date).strftime("%A")
    segs = "".join(
        f'<span class="seg{" on" if r["done"] else ""}"></span>' for r in rows)
    progress = (f'<div class="progress"><span class="segs">{segs}</span>'
                f'<span class="count">{done_n}/{len(rows)} worked</span></div>'
                if rows else "")
    build_label = ("Fetch more targets" if rows and date == today
                   else "Build today’s queue")
    disabled = " disabled" if building else ""
    manifest = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Daily queue · {weekday}</div>
    <h1>{date}</h1>
  </div>
  {progress}
  <form class="buildform" method="post" action="/build">
    <label class="opt"><input type="checkbox" name="notes" value="1"> draft notes</label>
    <button class="primary"{disabled}>{build_label}</button>
  </form>
</div>"""

    banner = ""
    if building:
        banner = '<p class="banner">Building queue — fetching job boards…</p>'
    elif error:
        banner = f'<p class="banner err">Last build failed: {esc(error)}</p>'

    datenav = ""
    if len(dates) > 1:
        links = [f'<a{" class=cur" if d == date else ""} href="/?date={d}">{d}</a>'
                 for d in dates]
        datenav = f'<nav class="dates">{"".join(links)}</nav>'

    items = []
    for r in rows:
        job = qa.Job(source=r["source"], title=r["title"], company=r["company"],
                     url=r["url"], location=r["location"])
        linkrow = [f'<a href="{esc(r["url"])}" target="_blank" '
                   f'rel="noopener">job post</a>']
        for label, url in qa.build_links(job, cfg).items():
            linkrow.append(f'<a href="{esc(url)}" target="_blank" '
                           f'rel="noopener">{esc(label)}</a>')
        meta_bits = [esc(r["title"])]
        if r["location"]:
            meta_bits.append(esc(r["location"]))
        meta_bits.append(esc(r["source"]))

        if r["note"]:
            note_html = (f'<p class="note">“{esc(r["note"])}”'
                         f'<span class="len">{len(r["note"])}/200</span></p>')
        elif r["uid"] in pending:
            note_html = '<p class="note pending">drafting note…</p>'
        else:
            note_html = (f'<form method="post" action="/note" style="margin:8px 0 0">'
                         f'<input type="hidden" name="date" value="{esc(date)}">'
                         f'<input type="hidden" name="uid" value="{esc(r["uid"])}">'
                         f'<button class="ghost">Draft connection note</button></form>')

        done = bool(r["done"])
        items.append(f"""
<article class="target{' done' if done else ''}">
  <form method="post" action="/toggle">
    <input type="hidden" name="date" value="{esc(date)}">
    <input type="hidden" name="uid" value="{esc(r['uid'])}">
    <button class="tick" aria-pressed="{'true' if done else 'false'}"
            title="mark worked">{'✓' if done else ''}</button>
  </form>
  <div style="flex:1">
    <h2>{esc(r['company'])} <span class="score">{r['score']:g}</span></h2>
    <p class="meta">{' · '.join(meta_bits)}</p>
    <p class="linkrow">{' '.join(linkrow)}</p>
    {note_html}
  </div>
</article>""")

    if not rows and not building:
        items.append('<p class="empty">No queue for this date. '
                     'Build one — the boards decide, you click.</p>')
    if rows:
        items.append('<p class="hint">Checklist per target: visit 2–3 profiles '
                     '→ connect with note → tick it off.</p>')

    return page(f"Queue {date}", "/", manifest + banner + datenav + "".join(items),
                refresh=building or bool(pending))


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


GET_ROUTES = {
    "/": page_queue,
    "/board": page_board,
    "/due": page_due,
    "/log": page_log,
    "/company": page_company,
}


# --------------------------------------------------------------------------- #
# HTTP handler
# --------------------------------------------------------------------------- #

class Handler(BaseHTTPRequestHandler):
    server_version = "linkedin-queue-web/1.0"

    def respond(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def origin_ok(self) -> bool:
        """Reject cross-site POSTs; same-origin forms send a matching Origin."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return origin == f"http://{self.headers.get('Host', '')}"

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        fn = GET_ROUTES.get(path)
        if fn is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.respond(fn(urllib.parse.parse_qs(query)))

    def do_POST(self) -> None:
        if not self.origin_ok():
            self.send_error(HTTPStatus.FORBIDDEN, "cross-origin POST rejected")
            return
        length = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        path = self.path.partition("?")[0]
        if path == "/build":
            self.post_build(form)
        elif path == "/toggle":
            self.post_toggle(form)
        elif path == "/note":
            self.post_note(form)
        elif path == "/add":
            self.post_add(form)
        elif path == "/done":
            self.post_done(form)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    # -- POST actions -------------------------------------------------------

    def post_build(self, form: dict[str, list[str]]) -> None:
        with BUILD_LOCK:
            if not BUILD["running"]:
                BUILD["running"] = True
                BUILD["error"] = ""
                threading.Thread(target=build_worker,
                                 args=("notes" in form,), daemon=True).start()
        self.redirect("/")

    def post_toggle(self, form: dict[str, list[str]]) -> None:
        date = form.get("date", [""])[0]
        uid = form.get("uid", [""])[0]
        conn = db()
        conn.execute(
            "UPDATE queue_items SET done = 1 - done WHERE date = ? AND uid = ?",
            (date, uid))
        conn.commit()
        conn.close()
        self.redirect(f"/?date={urllib.parse.quote(date)}")

    def post_note(self, form: dict[str, list[str]]) -> None:
        date = form.get("date", [""])[0]
        uid = form.get("uid", [""])[0]
        if uid:
            with NOTES_LOCK:
                fresh = uid not in NOTES_PENDING
                NOTES_PENDING.add(uid)
            if fresh:
                threading.Thread(target=note_worker, args=(date, uid),
                                 daemon=True).start()
        self.redirect(f"/?date={urllib.parse.quote(date)}")

    def post_add(self, form: dict[str, list[str]]) -> None:
        company = form.get("company", [""])[0].strip()
        if not company:
            self.redirect("/log")
            return
        action = form.get("action", ["visited"])[0]
        if action not in tracker.ACTIONS:
            action = "visited"
        person = form.get("person", [""])[0].strip() or None
        note = form.get("note", [""])[0].strip() or None
        followup = form.get("followup", [""])[0].strip()
        today = dt.date.today()
        due = ((today + dt.timedelta(days=int(followup))).isoformat()
               if followup.isdigit() else None)
        conn = db()
        company = tracker.resolve_company(conn, company)
        conn.execute(
            "INSERT INTO outreach (company, person, action, note, date, followup_due) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (company, person, action, note, today.isoformat(), due))
        conn.commit()
        conn.close()
        self.redirect(f"/company?name={urllib.parse.quote(company)}")

    def post_done(self, form: dict[str, list[str]]) -> None:
        raw = form.get("id", [""])[0]
        if raw.isdigit():
            conn = db()
            conn.execute("UPDATE outreach SET followup_done = 1 WHERE id = ?",
                         (int(raw),))
            conn.commit()
            conn.close()
        self.redirect("/due")


def main() -> int:
    cfg = qa.load_config()
    web = cfg.get("web", {})
    host = web.get("host", "127.0.0.1")
    port = int(web.get("port", 8765))
    # ensure both schemas exist before the first request
    qa.db_connect().close()
    tracker.db_connect().close()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"linkedin-queue web UI on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
