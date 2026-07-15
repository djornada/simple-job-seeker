"""Remotive — public JSON API, no auth. No LinkedIn automation."""

from __future__ import annotations

import json
import urllib.parse

from .base import Job, _get, strip_html


def fetch(cfg: dict) -> list[Job]:
    search_terms = cfg["sources"].get("remotive_searches", ["react"])
    jobs = []
    for term in search_terms:
        q = urllib.parse.quote(term)
        url = f"https://remotive.com/api/remote-jobs?search={q}&limit=50"
        data = json.loads(_get(url))
        for item in data.get("jobs", []):
            jobs.append(Job(
                source="remotive",
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                url=item.get("url", ""),
                tags=[t.lower() for t in item.get("tags", [])],
                location=item.get("candidate_required_location", ""),
                description=strip_html(item.get("description", "")),
            ))
    return jobs
