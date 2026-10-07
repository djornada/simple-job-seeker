"""Keyword scoring: gates first, role keyword in title required, stack
keywords add points."""
from __future__ import annotations

import re

from sources import Job

from .gates import check_gates


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]", " ", text.lower())


def score_job(job: Job, cfg: dict) -> float:
    """Score by keyword matches; return 0 to reject. Language and
    eligibility gates run first and leave their notes on `job.flags`."""
    job.gate, job.flags = check_gates(job, cfg)
    if job.gate:
        return 0.0
    f = cfg["filters"]
    haystack = _norm(f"{job.title} {' '.join(job.tags)}")
    title = _norm(job.title)

    for bad in f.get("exclude_keywords", []):
        if _norm(bad) in title:
            return 0.0

    if f.get("brazil_friendly_only", False) and job.location:
        loc = job.location.lower()
        ok_markers = ("worldwide", "anywhere", "latam", "latin america",
                      "americas", "brazil", "south america", "global", "remote")
        if not any(m in loc for m in ok_markers):
            return 0.0

    score = 0.0
    matched_role = False
    for kw in f.get("role_keywords", []):
        if _norm(kw) in title:
            score += 3.0
            matched_role = True
    for kw in f.get("stack_keywords", []):
        if _norm(kw) in haystack:
            score += 1.0

    if not matched_role:
        return 0.0
    return score
