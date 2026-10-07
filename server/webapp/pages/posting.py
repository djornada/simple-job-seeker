"""`/posting` — the archived text of one queued job, as first seen."""
from __future__ import annotations

from ..layout import page
from ..state import db, esc


def page_posting(params: dict[str, list[str]]) -> str:
    uid = params.get("uid", [""])[0]
    conn = db()
    row = conn.execute("SELECT * FROM postings WHERE uid = ?", (uid,)).fetchone()
    conn.close()
    if row is None:
        return page("Posting", "/",
                    '<p class="empty">No saved posting for this job. Jobs '
                    'queued before the archive existed have none.</p>')
    meta_bits = [esc(row["title"])]
    if row["location"]:
        meta_bits.append(esc(row["location"]))
    meta_bits.append(esc(row["source"]))
    status = ""
    if row["expired_at"]:
        status = (f' · <span class="expired">expired '
                  f'{esc(row["expired_at"][:10])}</span>')
    elif row["checked_at"]:
        status = f' · still up {esc(row["checked_at"][:10])}'
    head = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Saved posting · archived {esc(row['archived_at'][:10])}{status}</div>
    <h1>{esc(row['company'])}</h1>
    <p class="meta">{' · '.join(meta_bits)}</p>
    <p class="linkrow"><a href="{esc(row['url'])}" target="_blank"
       rel="noopener">original post</a></p>
  </div>
</div>"""
    body = f'<p class="posting">{esc(row["text"])}</p>'
    return page(f"{row['company']} posting", "/", head + body)
