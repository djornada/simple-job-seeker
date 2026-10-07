"""Queue selection: score, filter, dedupe (one job per company), cap."""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter

from db import is_new
from sources import Job

from .scoring import score_job


def select_queue(conn: sqlite3.Connection, jobs: list[Job], cfg: dict,
                 limit: int, cooldown: int) -> list[Job]:
    """Score, filter, dedupe (one job per company) and cap the queue."""
    for job in jobs:
        job.score = score_job(job, cfg)
    if cfg.get("gates"):
        gated = Counter(j.gate for j in jobs if j.gate)
        print(f"[gate] rejected {sum(gated.values())} "
              f"(language {gated['language']}, "
              f"eligibility {gated['eligibility']})", file=sys.stderr)
    candidates = [j for j in jobs if j.score > 0 and j.company and j.url]
    candidates.sort(key=lambda j: j.score, reverse=True)

    queue: list[Job] = []
    seen_companies: set[str] = set()
    for job in candidates:
        key = job.company.lower()
        if key in seen_companies:
            continue
        if not is_new(conn, job, cooldown):
            continue
        queue.append(job)
        seen_companies.add(key)
        if len(queue) >= limit:
            break
    return queue
