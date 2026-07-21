"""LinkedIn data-export ZIP → (profile_text, headline, skills).

Pure parsing: reads Profile.csv / Positions.csv / Skills.csv from the export
and builds a full profile text (every position, untruncated) so the model
gets real context. No I/O beyond the ZIP; nothing touches LinkedIn.
"""
from __future__ import annotations

import csv
import io
import zipfile


def _find_member(zf: zipfile.ZipFile, basename: str) -> str | None:
    want = basename.lower()
    for name in zf.namelist():
        if name.rsplit("/", 1)[-1].lower() == want:
            return name
    return None


def _read_csv(zf: zipfile.ZipFile, basename: str) -> list[dict]:
    name = _find_member(zf, basename)
    if not name:
        return []
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
        return list(csv.DictReader(text))


def _field(row: dict, *names: str) -> str:
    """Case-insensitive header lookup; returns the first non-empty match."""
    lower = {(k or "").strip().lower(): v for k, v in row.items()}
    for n in names:
        v = (lower.get(n.lower()) or "").strip()
        if v:
            return v
    return ""


def build_profile(zf: zipfile.ZipFile) -> tuple[str, str, list[str]]:
    """Return (profile_text, headline, skills).

    The experience is parsed in full — every position, full descriptions —
    so the model gets real context for the re-rank and for drafting notes.
    """
    profile_rows = _read_csv(zf, "Profile.csv")
    positions = _read_csv(zf, "Positions.csv")
    skills_rows = _read_csv(zf, "Skills.csv")

    headline = summary = ""
    if profile_rows:
        headline = _field(profile_rows[0], "Headline")
        summary = _field(profile_rows[0], "Summary")

    skills = [_field(r, "Name") for r in skills_rows]
    skills = [s for s in skills if s]

    parts: list[str] = []
    if headline:
        parts.append(f"Headline: {headline}")
    if summary:
        parts.append(f"Summary: {summary}")
    if positions:
        parts.append("Experience:")
        for r in positions:
            title = _field(r, "Title")
            company = _field(r, "Company Name")
            started = _field(r, "Started On")
            finished = _field(r, "Finished On") or "Present"
            desc = _field(r, "Description")
            when = f" ({started}–{finished})" if started else ""
            line = f"- {title} @ {company}{when}".rstrip()
            if desc:
                line += f": {desc}"
            parts.append(line)
    if skills:
        parts.append("Skills: " + ", ".join(skills))

    return "\n".join(parts), headline, skills
