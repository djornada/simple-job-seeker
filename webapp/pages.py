"""Page renderers, one per route. GET_ROUTES maps path → renderer."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import urllib.parse

import queue_agent as qa
import tracker

from .layout import page, timeline_row
from .state import (
    BUILD,
    BUILD_LOCK,
    DATE_RE,
    NOTES_FAILED,
    NOTES_LOCK,
    NOTES_PENDING,
    db,
    esc,
)


def page_queue(params: dict[str, list[str]]) -> str:
    conn = db()
    dates = [r[0] for r in conn.execute(
        "SELECT DISTINCT date FROM queue_items ORDER BY date DESC LIMIT 10")]
    today = dt.date.today().isoformat()
    date = params.get("date", [""])[0]
    if not DATE_RE.fullmatch(date):
        date = dates[0] if dates else today
    rows = conn.execute(
        "SELECT * FROM queue_items WHERE date = ? "
        "ORDER BY llm_score IS NULL, llm_score DESC, score DESC, company",
        (date,)).fetchall()
    prow = conn.execute(
        "SELECT headline FROM profile WHERE id = 1").fetchone()
    conn.close()

    cfg = qa.load_config()
    with BUILD_LOCK:
        building, error = BUILD["running"], BUILD["error"]
    with NOTES_LOCK:
        pending = set(NOTES_PENDING)
        failed = set(NOTES_FAILED)

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

        fit_html = ""
        if r["fit_note"]:
            band = (f'<span class="llm">fit {r["llm_score"]:g}/10</span>'
                    if r["llm_score"] is not None else "")
            fit_html = f'<p class="fit">{band}{esc(r["fit_note"])}</p>'

        if r["note"]:
            note_html = (f'<p class="note">“{esc(r["note"])}”'
                         f'<span class="len">{len(r["note"])}/200</span></p>')
        elif r["uid"] in pending:
            note_html = '<p class="note pending">drafting note…</p>'
        else:
            failed_html = (
                '<p class="note failed">draft failed — LLM unreachable or '
                'rate-limited (check the server log)</p>'
                if r["uid"] in failed else "")
            label = "Try again" if r["uid"] in failed else "Draft connection note"
            note_html = (f'{failed_html}'
                         f'<form method="post" action="/note" style="margin:8px 0 0">'
                         f'<input type="hidden" name="date" value="{esc(date)}">'
                         f'<input type="hidden" name="uid" value="{esc(r["uid"])}">'
                         f'<button class="ghost">{label}</button></form>')

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
    {fit_html}
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


def _best_stage_by_company(conn: sqlite3.Connection) -> dict[str, int]:
    """Furthest funnel stage reached per company (lower-cased name → weight)."""
    best: dict[str, int] = {}
    for r in conn.execute("SELECT company, action FROM outreach"):
        key = (r["company"] or "").lower()
        weight = tracker.STAGE_ORDER.get(r["action"], -1)
        if weight > best.get(key, -1):
            best[key] = weight
    return best


def _stats_table(header: str, rows: list[tuple]) -> str:
    """rows: list of (label, queued, contacted, replied)."""
    trs = []
    for label, queued, contacted, replied in rows:
        rate = f"{replied / queued:.0%}" if queued else "—"
        trs.append(
            f"<tr><td>{esc(label)}</td><td>{queued}</td><td>{contacted}</td>"
            f"<td>{replied}</td><td class='rate'>{rate}</td></tr>")
    return (f'<section class="stage"><h2>{esc(header)}</h2></section>'
            '<table class="stats"><thead><tr><th>source</th><th>queued</th>'
            '<th>contacted</th><th>replied</th><th>reply rate</th></tr></thead>'
            f'<tbody>{"".join(trs)}</tbody></table>')


def page_stats(_: dict[str, list[str]]) -> str:
    conn = db()
    qrows = conn.execute(
        "SELECT source, LOWER(company) AS company, llm_score "
        "FROM queue_items").fetchall()
    best = _best_stage_by_company(conn)
    conn.close()

    if not qrows:
        return page("Stats", "/stats",
                    '<p class="empty">No queue history yet. '
                    '<a href="/">Build a queue</a> first.</p>')

    contacted_w = tracker.STAGE_ORDER["connected"]
    replied_w = tracker.STAGE_ORDER["replied"]

    def tally(bucket: dict, key: str, company: str) -> None:
        st = bucket.setdefault(key, {"companies": set(), "contacted": set(),
                                     "replied": set()})
        st["companies"].add(company)
        stage = best.get(company, -1)
        if stage >= contacted_w:
            st["contacted"].add(company)
        if stage >= replied_w:
            st["replied"].add(company)

    by_source: dict[str, dict] = {}
    by_band: dict[str, dict] = {}
    BANDS = [(9, "9–10"), (7, "7–8"), (5, "5–6"), (0, "0–4")]
    have_llm = False
    for r in qrows:
        tally(by_source, r["source"], r["company"])
        if r["llm_score"] is not None:
            have_llm = True
            band = next(lbl for lo, lbl in BANDS if r["llm_score"] >= lo)
            tally(by_band, band, r["company"])

    def to_rows(bucket: dict, order: list | None = None) -> list[tuple]:
        keys = order if order else sorted(bucket)
        return [(k, len(bucket[k]["companies"]), len(bucket[k]["contacted"]),
                 len(bucket[k]["replied"])) for k in keys if k in bucket]

    src_rows = sorted(to_rows(by_source), key=lambda x: -x[1])
    body = _stats_table("effectiveness by source", src_rows)

    if have_llm:
        band_rows = to_rows(by_band, [lbl for _, lbl in BANDS])
        body += _stats_table("conversion by fit-score band", band_rows)

    body += ('<p class="caveat">Companies are matched between the queue and '
             'outreach log by lower-cased name — loose, but fine for personal '
             'tooling. “Contacted” = reached at least the connected stage; '
             '“replied” = the company answered.</p>')
    return page("Stats", "/stats", body)


UPLOAD_FORM = """
<form class="logform" method="post" action="/import" enctype="multipart/form-data">
  <label class="full">LinkedIn data export (.zip)
    <input type="file" name="resume" accept=".zip,application/zip" required>
  </label>
  <div class="full"><button class="primary">Import résumé</button></div>
</form>
<p class="hint">Get the ZIP from LinkedIn: <em>Settings &amp; Privacy → Data
Privacy → Get a copy of your data</em>, tick the larger archive (it holds
Profile, Positions, Skills), and download it. Then pick that file above —
nothing is sent to LinkedIn; the file is read locally and stored in
state.db.</p>"""


def page_profile(params: dict[str, list[str]]) -> str:
    conn = db()
    row = conn.execute(
        "SELECT text, headline, skills_json, imported_at "
        "FROM profile WHERE id = 1").fetchone()
    conn.close()

    banner = ""
    if params.get("ok"):
        banner = '<p class="banner">Résumé imported — the queue re-ranks on the next build.</p>'
    elif params.get("err"):
        banner = f'<p class="banner err">Import failed: {esc(params["err"][0])}</p>'

    if not row:
        head = """
<div class="manifest">
  <div>
    <div class="eyebrow">Résumé</div>
    <h1>No résumé imported</h1>
  </div>
</div>
<p class="hint">Import your LinkedIn export to re-rank the daily queue by real
fit against your experience and personalize connection notes.</p>"""
        return page("Résumé", "/profile", head + banner + UPLOAD_FORM)

    text, headline, skills_json, imported_at = row
    skills = json.loads(skills_json) if skills_json else []
    chips = "".join(f'<span class="score">{esc(s)}</span>' for s in skills)
    head = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Résumé · imported {esc(imported_at)}</div>
    <h1>{esc(headline or "Profile")}</h1>
  </div>
</div>"""
    body = (head + banner
            + f'<section class="stage"><h2>skills ({len(skills)})</h2></section>'
            + (f'<div class="chips">{chips}</div>' if chips else '')
            + '<section class="stage"><h2>profile text · fed to the re-rank</h2></section>'
            + f'<pre class="profiletext">{esc(text)}</pre>'
            + '<section class="stage"><h2>re-import</h2></section>'
            + UPLOAD_FORM)
    return page("Résumé", "/profile", body)


GET_ROUTES = {
    "/": page_queue,
    "/board": page_board,
    "/due": page_due,
    "/log": page_log,
    "/company": page_company,
    "/stats": page_stats,
    "/profile": page_profile,
}
