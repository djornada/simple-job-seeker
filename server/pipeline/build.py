"""The build use case shared by the CLI and the web UI's build button.

Collect jobs, score/filter/dedupe against state, and — when a résumé is
imported — re-rank the shortlist by real fit. Notes are deliberately not
drafted here: that's adapter policy (the CLI aborts on the first failure,
the web UI keeps going and marks failures per-item).
"""
from __future__ import annotations

import sqlite3

from sources import Job, collect_jobs

from .resume import load_profile_text, rerank_with_resume
from .select import select_queue


def build_queue(conn: sqlite3.Connection, cfg: dict, limit: int) -> list[Job]:
    cooldown = cfg["targets"].get("company_cooldown_days", 30)
    profile_text = load_profile_text(conn)
    pool = (max(limit, cfg.get("resume", {}).get("shortlist", 30))
            if profile_text else limit)
    candidates = select_queue(conn, collect_jobs(cfg), cfg, pool, cooldown)
    if profile_text:
        candidates = rerank_with_resume(candidates, profile_text, cfg)
    return candidates[:limit]
