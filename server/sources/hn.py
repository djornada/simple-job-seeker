from __future__ import annotations

import json
import urllib.error
import urllib.parse

from .base import Job, _get, strip_html

def is_live(url: str) -> bool | None:
    """A Who-is-hiring comment is gone when Algolia has no text for it
    (deleted, flagged or dead). The job itself may have closed while the
    comment stays up; that reads as live."""
    query = urllib.parse.urlsplit(url).query
    item_id = urllib.parse.parse_qs(query).get("id", [""])[0]
    if not item_id.isdigit():
        return None
    try:
        item = json.loads(_get(f"https://hn.algolia.com/api/v1/items/{item_id}"))
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except (OSError, ValueError):  # URLError, timeouts, bad JSON
        return None
    text = (item.get("text") or "").strip()
    return bool(text) and text not in ("[deleted]", "[flagged]", "[dead]")


def fetch(cfg: dict) -> list[Job]:
    q = urllib.parse.quote('"who is hiring"')
    search = json.loads(_get(
        "https://hn.algolia.com/api/v1/search_by_date?"
        f"tags=story,author_whoishiring&query={q}"))
    hits = search.get("hits", [])
    if not hits:
        return []
    thread = json.loads(_get(
        f"https://hn.algolia.com/api/v1/items/{hits[0]['objectID']}"))

    jobs = []
    for comment in thread.get("children") or []:
        raw = comment.get("text") or ""
        if not raw:
            continue
        text = strip_html(raw, None)
        description = text[:2000]
        if "remote" not in description.lower():
            continue
        # Conventional header line: "Company | Role | Location | ..."
        header = strip_html(raw.split("<p>", 1)[0], limit=300)
        parts = [p.strip() for p in header.split("|")]
        company = parts[0] if parts else ""
        if not company:
            continue
        jobs.append(Job(
            source="hn",
            title=parts[1] if len(parts) > 1 else "",
            company=company,
            url=f"https://news.ycombinator.com/item?id={comment['id']}",
            location=parts[2] if len(parts) > 2 else "",
            description=description,
            full_text=text,
        ))
    return jobs
