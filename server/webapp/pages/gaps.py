"""`/gaps` — skills the résumé fit keeps flagging as missing, across postings.

Aggregates `fit_json.missing_skills` (pipeline/fit.py) over a window of
queue days. Weighted score = sum of (1 − overall/100) per posting, so gaps
from weaker fits count more. Skills already in the imported profile are
dropped. Names go through `pipeline.keywords.normalize`, so `[keywords]
.aliases` variants merge.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.parse

from pipeline import load_profile_bits
from pipeline.keywords import alias_map, normalize
from utils import load_config

from ..layout import page
from ..state import db, esc

WINDOWS = ("30", "90", "all")


def page_gaps(params: dict[str, list[str]]) -> str:
    window = params.get("days", ["90"])[0]
    if window not in WINDOWS:
        window = "90"
    conn = db()
    sql = ("SELECT uid, company, date, fit_json FROM queue_items "
           "WHERE fit_json IS NOT NULL")
    args: tuple = ()
    if window != "all":
        since = dt.date.today() - dt.timedelta(days=int(window))
        sql, args = sql + " AND date >= ?", (since.isoformat(),)
    rows = conn.execute(sql + " ORDER BY date", args).fetchall()
    bits = load_profile_bits(conn)
    conn.close()

    aliases = alias_map(load_config())
    have = {normalize(s, aliases) for s in (bits[1] if bits else [])}
    latest = {r["uid"]: r for r in rows}  # a uid queued twice counts once
    gaps: dict[str, dict] = {}
    for r in latest.values():
        detail = json.loads(r["fit_json"])
        weight = 1 - float(detail.get("overall", 50)) / 100
        for skill in {normalize(s, aliases)
                      for s in detail.get("missing_skills", [])}:
            if not skill or skill in have:
                continue
            g = gaps.setdefault(skill, {"postings": 0, "weight": 0.0,
                                        "last": "", "companies": []})
            g["postings"] += 1
            g["weight"] += weight
            g["last"] = max(g["last"], r["date"])
            g["companies"].append((r["date"], r["company"]))

    nav = "".join(
        f'<a{" class=cur" if w == window else ""} href="/gaps?days={w}">'
        f'{"all time" if w == "all" else f"last {w} days"}</a>'
        for w in WINDOWS)
    head = (f'<section class="stage"><h2>skill gaps</h2></section>'
            f'<nav class="dates">{nav}</nav>')
    if not latest:
        return page("Gaps", "/gaps", head + (
            '<p class="empty">No fit breakdowns in this window yet. Gaps come '
            'from résumé fit scoring: <a href="/profile">import your '
            'résumé</a>, then build a queue.</p>'))
    if not gaps:
        return page("Gaps", "/gaps", head + (
            f'<p class="empty">No missing skills across {len(latest)} scored '
            'postings in this window (or all of them are in your profile).</p>'))

    trs = []
    for skill, g in sorted(gaps.items(),
                           key=lambda kv: (-kv[1]["weight"], -kv[1]["postings"],
                                           kv[0])):
        seen: list[str] = []
        for _, company in sorted(g["companies"], reverse=True):
            if company not in seen:
                seen.append(company)
        links = ", ".join(
            f'<a href="/company?name={urllib.parse.quote(c)}">{esc(c)}</a>'
            for c in seen[:3])
        trs.append(f"<tr><td>{esc(skill)}</td><td>{g['postings']}</td>"
                   f"<td class='rate'>{g['weight']:.2f}</td>"
                   f"<td>{g['last']}</td><td>{links}</td></tr>")
    table = ('<table class="stats"><thead><tr><th>skill</th><th>postings</th>'
             '<th>weighted</th><th>last seen</th><th>examples</th></tr></thead>'
             f'<tbody>{"".join(trs)}</tbody></table>')
    caveat = (f'<p class="caveat">Across {len(latest)} scored postings. '
              'Weighted = sum of (1 − overall fit / 100), so a gap in a weak '
              'fit counts more than one in a strong fit. Skills in your '
              'imported profile are left out; merge spellings with '
              '<code>[keywords].aliases</code> in config.toml.</p>')
    return page("Gaps", "/gaps", head + table + caveat)
