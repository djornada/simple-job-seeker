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
    head = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">Saved posting · archived {esc(row['archived_at'][:10])}</div>
    <h1>{esc(row['company'])}</h1>
    <p class="meta">{' · '.join(meta_bits)}</p>
    <p class="linkrow"><a href="{esc(row['url'])}" target="_blank"
       rel="noopener">original post</a></p>
  </div>
</div>"""
    body = f'<p class="posting">{esc(row["text"])}</p>'
    return page(f"{row['company']} posting", "/", head + body)
