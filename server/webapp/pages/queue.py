"""`/` — the daily queue: check off targets, draft notes, rebuild."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import urllib.parse

from pipeline import build_links
from sources import Job
from utils import load_config

from ..layout import page
from ..state import (
    BUILD,
    BUILD_LOCK,
    DATE_RE,
    NOTES_FAILED,
    NOTES_LOCK,
    NOTES_PENDING,
    db,
    esc,
)


# Queue rows plus whether the posting text is archived (the card links it).
ITEM_SELECT = ("SELECT q.*, EXISTS(SELECT 1 FROM postings p WHERE p.uid = q.uid) "
               "AS archived FROM queue_items q")


def note_block(date: str, uid: str, note: str | None, pending: bool,
               failed: bool) -> str:
    """The note area for one item: existing note, pending, or draft button.

    Carries its own `hx-get` poll while pending; the poll response omits
    that attribute once the note resolves, so `outerHTML` swaps stop it.
    """
    if note:
        inner = (f'<p class="note">“{esc(note)}”'
                 f'<span class="len">{len(note)}/200</span></p>')
    elif pending:
        inner = '<p class="note pending">drafting note…</p>'
    else:
        failed_html = (
            '<p class="note failed">draft failed — LLM unreachable or '
            'rate-limited (check the server log)</p>' if failed else "")
        label = "Try again" if failed else "Draft connection note"
        inner = (f'{failed_html}'
                 f'<form method="post" action="/note" style="margin:8px 0 0">'
                 f'<input type="hidden" name="date" value="{esc(date)}">'
                 f'<input type="hidden" name="uid" value="{esc(uid)}">'
                 f'<button class="ghost">{label}</button></form>')
    poll = ""
    if pending:
        qs = urllib.parse.urlencode({"date": date, "uid": uid})
        poll = f' hx-get="/note-status?{qs}" hx-trigger="every 3s" hx-swap="outerHTML"'
    return f'<div class="notewrap"{poll}>{inner}</div>'


def render_item(r: sqlite3.Row, date: str, cfg: dict, pending: bool,
                failed: bool) -> str:
    """One queue target's card — shared by the full page render and the
    htmx fragment response after a toggle."""
    job = Job(source=r["source"], title=r["title"], company=r["company"],
             url=r["url"], location=r["location"])
    linkrow = [f'<a href="{esc(r["url"])}" target="_blank" '
               f'rel="noopener">job post</a>']
    if r["archived"]:
        qs = urllib.parse.urlencode({"uid": r["uid"]})
        linkrow.append(f'<a href="/posting?{esc(qs)}">saved posting</a>')
    for label, url in build_links(job, cfg).items():
        linkrow.append(f'<a href="{esc(url)}" target="_blank" '
                       f'rel="noopener">{esc(label)}</a>')
    meta_bits = [esc(r["title"])]
    if r["location"]:
        meta_bits.append(esc(r["location"]))
    meta_bits.append(esc(r["source"]))

    fit_html = ""
    if r["fit_note"]:
        band = (f'<span class="llm">fit {r["llm_score"]:g}/10</span>'
                if r["llm_score"] is not None else "")
        fit_html = f'<p class="fit">{band}{esc(r["fit_note"])}</p>'
    flags = json.loads(r["flags"]) if r["flags"] else []
    flags_html = (
        '<p class="flags">'
        + "".join(f'<span class="flag">{esc(f)}</span>' for f in flags)
        + "</p>") if flags else ""

    done = bool(r["done"])
    return f"""
<article class="target{' done' if done else ''}">
  <form method="post" action="/toggle"
        hx-post="/toggle" hx-target="closest article" hx-swap="outerHTML">
    <input type="hidden" name="date" value="{esc(date)}">
    <input type="hidden" name="uid" value="{esc(r['uid'])}">
    <button class="tick" aria-pressed="{'true' if done else 'false'}"
            title="mark worked">{'✓' if done else ''}</button>
  </form>
  <div style="flex:1">
    <h2>{esc(r['company'])} <span class="score">{r['score']:g}</span></h2>
    <p class="meta">{' · '.join(meta_bits)}</p>
    <p class="linkrow">{' '.join(linkrow)}</p>
    {fit_html}
    {flags_html}
    {note_block(date, r['uid'], r['note'], pending, failed)}
  </div>
</article>"""


def _build_section(date: str, rows: list[sqlite3.Row], prow: sqlite3.Row | None,
                   building: bool, error: str) -> str:
    """Manifest header + progress + build form + status banner, wrapped in
    one polled element. Shared by the full page render, `POST /build`'s
    htmx response, and `GET /build-status`."""
    today = dt.date.today().isoformat()
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
    resume = (f' · <a href="/profile">résumé: {esc(prow["headline"] or "imported")}</a>'
              if prow else ' · <a href="/profile">no résumé imported</a>')
    manifest = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Daily queue · {weekday}{resume}</div>
    <h1>{date}</h1>
  </div>
  {progress}
  <form class="buildform" method="post" action="/build"
        hx-post="/build" hx-target="#build-status" hx-swap="outerHTML">
    <input type="hidden" name="date" value="{esc(date)}">
    <label class="opt"><input type="checkbox" name="notes" value="1"> draft notes</label>
    <button class="primary"{disabled}>{build_label}</button>
  </form>
</div>"""

    banner = ""
    if building:
        banner = '<p class="banner">Building queue — fetching job boards…</p>'
    elif error:
        banner = f'<p class="banner err">Last build failed: {esc(error)}</p>'

    poll = (f' hx-get="/build-status?date={urllib.parse.quote(date)}" '
            'hx-trigger="every 3s" hx-swap="outerHTML"') if building else ""
    return f'<div id="build-status"{poll}>{manifest}{banner}</div>'


def get_note_status(params: dict[str, list[str]]) -> str:
    """`/note-status` — polled by `note_block` while a draft is pending."""
    date = params.get("date", [""])[0]
    uid = params.get("uid", [""])[0]
    conn = db()
    row = conn.execute(
        "SELECT note FROM queue_items WHERE date = ? AND uid = ?",
        (date, uid)).fetchone()
    conn.close()
    if row is None:
        return ""  # item gone; empty swap, polling stops naturally
    with NOTES_LOCK:
        pending, failed = uid in NOTES_PENDING, uid in NOTES_FAILED
    return note_block(date, uid, row["note"], pending, failed)


def get_build_status(params: dict[str, list[str]]) -> str:
    """`/build-status` — polled by `_build_section` while a build runs;
    also what `POST /build` returns directly to an htmx caller."""
    date = params.get("date", [""])[0]
    if not DATE_RE.fullmatch(date):
        date = dt.date.today().isoformat()
    conn = db()
    rows = conn.execute(
        "SELECT * FROM queue_items WHERE date = ? "
        "ORDER BY llm_score IS NULL, llm_score DESC, score DESC, company",
        (date,)).fetchall()
    prow = conn.execute("SELECT headline FROM profile WHERE id = 1").fetchone()
    conn.close()
    with BUILD_LOCK:
        building, error = BUILD["running"], BUILD["error"]
    return _build_section(date, rows, prow, building, error)


def page_queue(params: dict[str, list[str]]) -> str:
    conn = db()
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM queue_items ORDER BY date DESC LIMIT 10")]
    today = dt.date.today().isoformat()
    date = params.get("date", [""])[0]
    if not DATE_RE.fullmatch(date):
        date = dates[0] if dates else today
    rows = conn.execute(
        f"{ITEM_SELECT} WHERE date = ? "
        "ORDER BY llm_score IS NULL, llm_score DESC, score DESC, company",
        (date,)).fetchall()
    prow = conn.execute(
        "SELECT headline FROM profile WHERE id = 1").fetchone()
    conn.close()

    cfg = load_config()
    with BUILD_LOCK:
        building, error = BUILD["running"], BUILD["error"]
    with NOTES_LOCK:
        pending = set(NOTES_PENDING)
        failed = set(NOTES_FAILED)

    build_section = _build_section(date, rows, prow, building, error)

    datenav = ""
    if len(dates) > 1:
        links = [f'<a{" class=cur" if d == date else ""} href="/?date={d}">{d}</a>'
                 for d in dates]
        datenav = f'<nav class="dates">{"".join(links)}</nav>'

    items = [render_item(r, date, cfg, r["uid"] in pending, r["uid"] in failed)
             for r in rows]

    if not rows and not building:
        items.append('<p class="empty">No queue for this date. '
                     'Build one — the boards decide, you click.</p>')
    if rows:
        items.append('<p class="hint">Checklist per target: visit 2–3 profiles '
                     '→ connect with note → tick it off.</p>')

    return page(f"Queue {date}", "/", build_section + datenav + "".join(items))
