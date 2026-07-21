"""`/stats` — source + fit-score effectiveness against the outreach funnel."""
from __future__ import annotations

import sqlite3

import tracker

from ..layout import page
from ..state import db, esc


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
