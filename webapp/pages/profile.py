"""`/profile` — view the imported résumé, upload/replace the export ZIP."""
from __future__ import annotations

import json

from ..layout import page
from ..state import db, esc

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
