from __future__ import annotations

import json
import urllib.parse

from .base import Job, _get, strip_html

# freehire.me merges ~50 ATS boards (Greenhouse, Lever, Ashby, Gupy,
# GetOnBrd, ...) into one public JSON API. The agent search returns each
# hit's full description, so one request per search term is enough.
API = "https://freehire.me/api/v1/agent/jobs/search"


def _location(item: dict) -> str:
    """The ATS's free-text location plus what freehire resolved from it
    ("Worldwide" for a global role, "Brazil" when it lists Brazil), so the
    `brazil_friendly_only` filter sees them. A bare LATAM country stays
    as-is: "Costa Rica" doesn't mean Brazil can apply."""
    loc = item.get("location") or ""
    extra = []
    if "global" in (item.get("regions") or []):
        extra.append("Worldwide")
    if "br" in (item.get("countries") or []) and "brazil" not in loc.lower():
        extra.append("Brazil")
    return ", ".join(p for p in [loc, *extra] if p)


def fetch(cfg: dict) -> list[Job]:
    src = cfg["sources"]
    params = {
        "work_mode": "remote",
        "regions": src.get("freehire_regions", ["latam", "global"]),
        "countries": src.get("freehire_countries", ["br"]),
        "posted_within_days": src.get("freehire_days", 14),
        "description_format": "html",
        "limit": 50,
    }
    skip = tuple(src.get("freehire_skip", []))
    jobs = []
    for term in src.get("freehire_searches", ["react"]):
        query = urllib.parse.urlencode({**params, "q": term}, doseq=True)
        data = json.loads(_get(f"{API}?{query}"))
        for item in data.get("data") or []:
            if skip and (item.get("source") or "").startswith(skip):
                continue
            text = strip_html(item.get("description", ""), None)
            jobs.append(Job(
                source="freehire",
                title=item.get("title", ""),
                company=item.get("company", ""),
                url=item.get("url", ""),
                tags=[t.lower() for t in item.get("skills") or []],
                location=_location(item),
                description=text[:2000],
                full_text=text,
            ))
    return jobs
