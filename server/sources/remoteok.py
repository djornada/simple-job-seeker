from __future__ import annotations

import json

from .base import Job, _get, strip_html

def fetch(cfg: dict) -> list[Job]:
    data = json.loads(_get("https://remoteok.com/api"))
    jobs = []
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue  # first element is API metadata
        text = strip_html(item.get("description", ""), None)
        jobs.append(Job(
            source="remoteok",
            title=item.get("position", ""),
            company=item.get("company", ""),
            url=item.get("url", ""),
            tags=[t.lower() for t in item.get("tags", [])],
            location=item.get("location", ""),
            description=text[:2000],
            full_text=text,
        ))
    return jobs
