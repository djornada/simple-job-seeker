"""Rate ad-hoc jobs/posts submitted by the browser extension.

Scores against the same keyword filters and — when a résumé is imported —
the same LLM fit-judge as the board pipeline, then persists anything that
clears the bar into today's queue. A job a language/eligibility gate
rejects skips the LLM call and is never queued. The third use case built
from these stages, alongside build_queue: same scoring/persistence,
different input (one externally-supplied batch instead of a job-board
fetch).
"""
from __future__ import annotations

import sqlite3

from db import save_queue
from sources import Job

from .resume import judge_fit, load_profile_text
from .scoring import score_job


def rate_jobs(conn: sqlite3.Connection, jobs: list[Job], cfg: dict) -> list[Job]:
    profile_text = load_profile_text(conn)
    floor = cfg.get("resume", {}).get("min_llm_score", 5)
    for job in jobs:
        job.score = score_job(job, cfg)
        if profile_text and not job.gate:
            result = judge_fit(job, profile_text, cfg)
            if result is not None:
                job.llm_score = result.get("score", 0.0)
                job.fit_note = result.get("fit", "")
                job.fit_detail = result.get("detail", {})

    queued = [j for j in jobs if not j.gate
              and (j.score > 0 or (j.llm_score or 0) >= floor)]
    if queued:
        save_queue(conn, queued, {})
    return jobs
