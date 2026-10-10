"""`/` — the daily queue: check off targets, draft notes, check keyword
coverage, rebuild."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sqlite3
import urllib.parse

import tracker
from pipeline import NOTE_LIMIT, build_links
from sources import Job
from utils import load_config

from ..layout import page
from ..state import (
    BUILD,
    BUILD_LOCK,
    COVERAGE_FAILED,
    COVERAGE_LOCK,
    COVERAGE_PENDING,
    DATE_RE,
    NOTES_FAILED,
    NOTES_LOCK,
    NOTES_PENDING,
    db,
    esc,
)
from .logform import log_button, log_dialog, log_form


# Queue rows plus whether the posting text is archived, when it was found
# expired, the application made from it, if any, and whether a résumé is
# imported (the card shows all; the last two gate "Check keywords").
ITEM_SELECT = ("SELECT q.*, EXISTS(SELECT 1 FROM postings p WHERE p.uid = q.uid) "
               "AS archived, (SELECT p.expired_at FROM postings p "
               "WHERE p.uid = q.uid) AS expired_at, (SELECT a.id FROM "
               "applications a WHERE a.uid = q.uid LIMIT 1) AS app_id, "
               "EXISTS(SELECT 1 FROM profile) AS profiled "
               "FROM queue_items q")
# The queue page's card order; cards streamed in during a build follow it.
CARD_ORDER = ("expired_at IS NOT NULL, llm_score IS NULL, llm_score DESC, "
              "score DESC, company")
CARD_ID_RE = re.compile(r"t-[0-9a-f]{12}")


def note_block(date: str, uid: str, note: str | None, pending: bool,
               failed: bool) -> str:
    """The note area for one item: pending, or the last failure, existing
    note and a draft / redraft / retry button.

    Carries its own `hx-get` poll while pending; the poll response omits
    that attribute once the note resolves, so `outerHTML` swaps stop it.
    A failed redraft keeps the old note (note_worker only writes on
    success), so it shows under the failure line.
    """
    if pending:
        inner = '<p class="note pending">drafting note…</p>'
    else:
        failed_html = (
            '<p class="note failed">draft failed — LLM unreachable or '
            'rate-limited (check the server log)</p>' if failed else "")
        note_html = (f'<p class="note">“{esc(note)}”'
                     f'<span class="len">{len(note)}/{NOTE_LIMIT}</span></p>'
                     if note else "")
        label = ("Try again" if failed else
                 "Redraft" if note else "Draft connection note")
        inner = (f'{failed_html}{note_html}'
                 f'<form method="post" action="/note" hx-post="/note" '
                 f'hx-target="closest .notewrap" hx-swap="outerHTML" '
                 f'style="margin:{"4px" if note else "8px"} 0 0">'
                 f'<input type="hidden" name="date" value="{esc(date)}">'
                 f'<input type="hidden" name="uid" value="{esc(uid)}">'
                 f'<button class="{"linkbtn" if note else "ghost"}">{label}'
                 f'</button></form>')
    poll = ""
    if pending:
        qs = urllib.parse.urlencode({"date": date, "uid": uid})
        poll = f' hx-get="/note-status?{qs}" hx-trigger="every 3s" hx-swap="outerHTML"'
    return f'<div class="notewrap"{poll}>{inner}</div>'


def coverage_state(uid: str) -> tuple[bool, str]:
    """(check in flight, why the last one failed or "") for one item."""
    with COVERAGE_LOCK:
        return uid in COVERAGE_PENDING, COVERAGE_FAILED.get(uid, "")


def coverage_block(date: str, uid: str, coverage: dict, can_check: bool,
                   pending: bool, error: str, show: bool = False) -> str:
    """Keyword coverage for one item (pipeline/coverage.py): the terms
    table once checked, a pending line while the worker runs, the last
    failure, and a check button when there's a saved posting and a résumé.

    Polls `/coverage-status` while pending, like `note_block`; `show`
    opens the table (set by the poll response that delivers it).
    """
    form = ""
    if can_check:
        label = ("Try again" if error else
                 "Check again" if coverage else "Check keywords")
        form = (f'<form method="post" action="/coverage" hx-post="/coverage" '
                f'hx-target="closest .covwrap" hx-swap="outerHTML" '
                f'style="margin:6px 0 0">'
                f'<input type="hidden" name="date" value="{esc(date)}">'
                f'<input type="hidden" name="uid" value="{esc(uid)}">'
                f'<button class="ghost" title="keywords the posting asks for '
                f'vs your résumé">{label}</button></form>')
    if pending:
        inner = '<p class="note pending">checking keywords…</p>'
    else:
        inner = (f'<p class="note failed">keyword check failed — {esc(error)}'
                 f'</p>' if error else "")
        terms = coverage.get("terms", [])
        if terms:
            counts = []
            for kind in ("required", "preferred"):
                rows = [t for t in terms if t["kind"] == kind]
                if rows:
                    hit = sum(t["status"] != "missing" for t in rows)
                    counts.append(f"{hit}/{len(rows)} {kind}")
            trs = "".join(
                f'<tr><td>{esc(t["term"])}</td>'
                f'<td class="kind">{esc(t["kind"])}</td>'
                f'<td><span class="kw kw-{esc(t["status"])}">'
                f'{esc(t["status"])}</span></td></tr>' for t in terms)
            inner += (f'<details class="fitmore"{" open" if show else ""}>'
                      f'<summary>keyword coverage: {", ".join(counts)}'
                      f'</summary><table class="kwtab">{trs}</table>{form}'
                      f'</details>')
        else:
            inner += form
    if not inner:
        return ""
    poll = ""
    if pending:
        qs = urllib.parse.urlencode({"date": date, "uid": uid})
        poll = (f' hx-get="/coverage-status?{qs}" hx-trigger="every 3s" '
                'hx-swap="outerHTML"')
    return f'<div class="covwrap"{poll}>{inner}</div>'


def _fit_block(detail: dict, note: str) -> str:
    """Verdict chip + fit line, and a <details> with the per-dimension
    scores, strengths, gaps and missing skills (pipeline/fit.py)."""
    v = detail.get("verdict", "")
    chip = (f'<span class="verdict v-{esc(v)}">{esc(v)} '
            f'{detail.get("overall", 0):g}</span>')
    dims = " · ".join(f"{esc(d)} {s:g}"
                      for d, s in detail.get("dimensions", {}).items())
    parts = [f'<p class="dims">{dims}</p>'] if dims else []
    for key, label in (("strengths", "strengths"), ("gaps", "gaps")):
        if detail.get(key):
            items = "".join(f"<li>{esc(x)}</li>" for x in detail[key])
            parts.append(f'<p class="dims">{label}</p><ul>{items}</ul>')
    if detail.get("missing_skills"):
        parts.append(f'<p class="dims">missing: '
                     f'{esc(", ".join(detail["missing_skills"]))}</p>')
    more = (f'<details class="fitmore"><summary>fit breakdown</summary>'
            f'{"".join(parts)}</details>') if parts else ""
    return f'<p class="fit">{chip}{esc(note)}</p>{more}'


def card_id(uid: str) -> str:
    """A queue card's element id (uids are `source:url`, not id-safe)."""
    return "t-" + hashlib.sha256(uid.encode()).hexdigest()[:12]


def log_prompt(conn: sqlite3.Connection, r: sqlite3.Row, date: str) -> str:
    """For a card just ticked worked: the log dialog, filled in with its
    company and `connected`, as an htmx out-of-band swap. Saving swaps the
    card back in, so you stay on the queue. Nothing if the company already
    has a touchpoint today; it only ever offers, never logs."""
    company = tracker.resolve_company(conn, r["company"])
    if conn.execute(
            "SELECT 1 FROM outreach WHERE lower(company) = lower(?) AND date = ?",
            (company, dt.date.today().isoformat())).fetchone():
        return ""
    form = log_form(r["company"], "connected", f"#{card_id(r['uid'])}",
                    {"date": date, "uid": r["uid"]})
    return f'<div hx-swap-oob="innerHTML:#logdlg">{form}</div>'


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
    linkrow.append(log_button(r["company"], "Log", "linkbtn"))
    if r["app_id"]:
        linkrow.append(f'<a href="/applications#app-{r["app_id"]}">applied ✓</a>')
    else:
        linkrow.append(
            f'<form class="inline" method="post" action="/apply" hx-post="/apply" '
            f'hx-target="closest article" hx-swap="outerHTML">'
            f'<input type="hidden" name="date" value="{esc(date)}">'
            f'<input type="hidden" name="uid" value="{esc(r["uid"])}">'
            f'<button class="linkbtn" title="track it on /applications">'
            f'I applied</button></form>')
    meta_bits = [esc(r["title"])]
    if r["location"]:
        meta_bits.append(esc(r["location"]))
    meta_bits.append(esc(r["source"]))
    if r["expired_at"]:
        meta_bits.append(f'<span class="expired" title="the board took the '
                         f'post down">expired {esc(r["expired_at"][:10])}</span>')

    fit_html = ""
    detail = json.loads(r["fit_json"]) if r["fit_json"] else {}
    if detail:
        fit_html = _fit_block(detail, r["fit_note"] or "")
    elif r["fit_note"]:
        band = (f'<span class="llm">fit {r["llm_score"]:g}/10</span>'
                if r["llm_score"] is not None else "")
        fit_html = f'<p class="fit">{band}{esc(r["fit_note"])}</p>'
    coverage = json.loads(r["coverage_json"]) if r["coverage_json"] else {}
    cov_pending, cov_error = coverage_state(r["uid"])
    coverage_html = coverage_block(
        date, r["uid"], coverage, bool(r["archived"] and r["profiled"]),
        cov_pending, cov_error)
    flags = json.loads(r["flags"]) if r["flags"] else []
    flags_html = (
        '<p class="flags">'
        + "".join(f'<span class="flag">{esc(f)}</span>' for f in flags)
        + "</p>") if flags else ""

    done = bool(r["done"])
    return f"""
<article class="target{' done' if done else ''}" id="{card_id(r['uid'])}">
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
    <div class="linkrow">{' '.join(linkrow)}</div>
    {fit_html}
    {flags_html}
    {coverage_html}
    {note_block(date, r['uid'], r['note'], pending, failed)}
  </div>
</article>"""


def progress_bar(rows: list[sqlite3.Row], oob: bool = False) -> str:
    """The "N/M worked" tracker in the queue's header, one segment per card.
    With `oob`, an htmx out-of-band swap, so a tick updates it alongside the
    card it re-renders."""
    if not rows:
        return ""
    done_n = sum(r["done"] for r in rows)
    segs = "".join(
        f'<span class="seg{" on" if r["done"] else ""}"></span>' for r in rows)
    swap = ' hx-swap-oob="true"' if oob else ""
    return (f'<div class="progress" id="progress"{swap}>'
            f'<span class="segs">{segs}</span>'
            f'<span class="count">{done_n}/{len(rows)} worked</span></div>')


def progress_oob(conn: sqlite3.Connection, date: str) -> str:
    """`progress_bar` for `date`'s queue, as an out-of-band swap."""
    rows = conn.execute(f"{ITEM_SELECT} WHERE date = ? ORDER BY {CARD_ORDER}",
                        (date,)).fetchall()
    return progress_bar(rows, oob=True)


def _build_section(date: str, rows: list[sqlite3.Row], prow: sqlite3.Row | None,
                   building: bool, error: str, stage: str = "") -> str:
    """Manifest header + progress + build form + status banner, wrapped in
    one polled element. Shared by the full page render, `POST /build`'s
    htmx response, and `GET /build-status`. `stage` is the worker's
    `BUILD["progress"]` ("scoring fit 12/45"), shown while building."""
    today = dt.date.today().isoformat()
    weekday = dt.date.fromisoformat(date).strftime("%A")
    progress = progress_bar(rows)
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
    <label class="opt" title="one LLM call per target; or draft per card"><input
      type="checkbox" name="notes" value="1"> draft notes</label>
    <button class="primary"{disabled}>{build_label}</button>
  </form>
</div>"""

    banner = ""
    if building:
        banner = (f'<p class="banner">Building queue — '
                  f'{esc(stage or "fetching job boards")}…</p>')
    elif error:
        banner = f'<p class="banner err">Last build failed: {esc(error)}</p>'

    # each poll says which cards the page has, so the reply can add the new
    # ones and drop the gone ones (`_card_changes`)
    poll = (f' hx-get="/build-status?date={urllib.parse.quote(date)}" '
            'hx-trigger="every 3s" hx-swap="outerHTML" hx-vals=\'js:{have: '
            '[...document.querySelectorAll("#items > article")]'
            '.map(a => a.id).join(" ")}\'') if building else ""
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


def get_coverage_status(params: dict[str, list[str]]) -> str:
    """`/coverage-status` — polled by `coverage_block` while a check runs;
    also what `POST /coverage` returns directly to an htmx caller."""
    date = params.get("date", [""])[0]
    uid = params.get("uid", [""])[0]
    conn = db()
    row = conn.execute(f"{ITEM_SELECT} WHERE date = ? AND uid = ?",
                       (date, uid)).fetchone()
    conn.close()
    if row is None:
        return ""  # item gone; empty swap, polling stops naturally
    coverage = json.loads(row["coverage_json"]) if row["coverage_json"] else {}
    pending, error = coverage_state(uid)
    return coverage_block(date, uid, coverage,
                          bool(row["archived"] and row["profiled"]),
                          pending, error, show=True)


def _card_changes(rows: list[sqlite3.Row], date: str, have: set[str]) -> str:
    """Out-of-band swaps that bring the page's cards (`have`, by id) up to
    `rows`: each new card goes in before the next card the page already
    shows, gone ones are deleted. Cards already there aren't touched, so
    their open details and in-flight polls survive."""
    ids = [card_id(r["uid"]) for r in rows]
    kept = have & set(ids)
    cfg = load_config()
    with NOTES_LOCK:
        pending, failed = set(NOTES_PENDING), set(NOTES_FAILED)
    out = []
    for i, r in enumerate(rows):
        if ids[i] in have:
            continue
        nxt = next((c for c in ids[i + 1:] if c in kept), None)
        where = f"beforebegin:#{nxt}" if nxt else "beforeend:#items"
        card = render_item(r, date, cfg, r["uid"] in pending, r["uid"] in failed)
        out.append(f'<div hx-swap-oob="{where}">{card}</div>')
    out += [f'<div id="{c}" hx-swap-oob="delete"></div>'
            for c in sorted(have - set(ids))]
    return "".join(out)


def get_build_status(params: dict[str, list[str]]) -> str:
    """`/build-status` — polled by `_build_section` while a build runs, with
    `have` (the page's card ids) so the reply also streams cards in; the
    last poll, once the build is done, leaves the page matching a reload.
    Also what `POST /build` returns directly to an htmx caller."""
    date = params.get("date", [""])[0]
    if not DATE_RE.fullmatch(date):
        date = dt.date.today().isoformat()
    conn = db()
    rows = conn.execute(f"{ITEM_SELECT} WHERE date = ? ORDER BY {CARD_ORDER}",
                        (date,)).fetchall()
    prow = conn.execute("SELECT headline FROM profile WHERE id = 1").fetchone()
    conn.close()
    with BUILD_LOCK:
        building, error = BUILD["running"], BUILD["error"]
        stage = BUILD["progress"]
    section = _build_section(date, rows, prow, building, error, stage)
    if "have" not in params:
        return section
    have = set(CARD_ID_RE.findall(params["have"][0]))
    return section + _card_changes(rows, date, have)


def page_queue(params: dict[str, list[str]]) -> str:
    conn = db()
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM queue_items ORDER BY date DESC LIMIT 10")]
    today = dt.date.today().isoformat()
    date = params.get("date", [""])[0]
    if not DATE_RE.fullmatch(date):
        date = dates[0] if dates else today
    rows = conn.execute(f"{ITEM_SELECT} WHERE date = ? ORDER BY {CARD_ORDER}",
                        (date,)).fetchall()
    prow = conn.execute(
        "SELECT headline FROM profile WHERE id = 1").fetchone()
    conn.close()

    cfg = load_config()
    with BUILD_LOCK:
        building, error = BUILD["running"], BUILD["error"]
        stage = BUILD["progress"]
    with NOTES_LOCK:
        pending = set(NOTES_PENDING)
        failed = set(NOTES_FAILED)

    build_section = _build_section(date, rows, prow, building, error, stage)

    datenav = ""
    if len(dates) > 1:
        links = [f'<a{" class=cur" if d == date else ""} href="/?date={d}">{d}</a>'
                 for d in dates]
        datenav = f'<nav class="dates">{"".join(links)}</nav>'

    cards = "".join(render_item(r, date, cfg, r["uid"] in pending,
                                r["uid"] in failed) for r in rows)
    if not rows:  # hidden by CSS once a build streams a card in
        cards = ('<p class="empty">No queue for this date. '
                 'Build one — the boards decide, you click.</p>')
    hint = ('<p class="hint">Checklist per target: visit 2–3 profiles '
            '→ connect with note → tick it off.</p>') if rows else ""

    return page(f"Queue {date}", "/",
                log_dialog() + build_section + datenav
                + f'<div id="items">{cards}</div>' + hint)
