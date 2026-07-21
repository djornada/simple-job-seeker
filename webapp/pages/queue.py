"""`/` — the daily queue: check off targets, draft notes, rebuild."""
from __future__ import annotations

import datetime as dt

import queue_agent as qa

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
