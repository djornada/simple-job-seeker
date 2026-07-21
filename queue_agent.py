#!/usr/bin/env python3
"""
Daily LinkedIn target queue builder.

Fetches remote job boards (RemoteOK, Remotive, We Work Remotely), filters
roles that match your profile, deduplicates against a local SQLite state,
and emits a daily queue of companies with prebuilt LinkedIn search links.

You do the clicking. The script does the deciding.

This module is the entrypoint + facade: it wires the pipeline stages
(scoring, links, llm, resume, render, db) and re-exports them so `qa.*`
keeps working for the web UI. The stages live in their own modules.

Usage:
    python queue_agent.py              # build today's queue
    python queue_agent.py --notes      # also draft connection notes via the LLM
    python queue_agent.py --dry-run    # don't persist state
    python queue_agent.py --stats      # show pipeline stats
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys

from db import db_connect, is_new, mark_queued, save_queue  # noqa: F401 — re-exported as qa.*
from links import build_links
from render import render, show_stats
from resume import (  # noqa: F401 — load_profile_bits re-exported as qa.*
    draft_note,
    load_profile_bits,
    load_profile_text,
    rerank_with_resume,
)
from scoring import score_job
from sources import Job, collect_jobs
from utils import DB_PATH, OUT_DIR, load_config  # noqa: F401 — DB_PATH re-exported as qa.*


def select_queue(conn: sqlite3.Connection, jobs: list[Job], cfg: dict,
                 limit: int, cooldown: int) -> list[Job]:
    """Score, filter, dedupe (one job per company) and cap the queue."""
    for job in jobs:
        job.score = score_job(job, cfg)
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Build today's LinkedIn target queue.")
    ap.add_argument("--notes", action="store_true", help="draft connection notes via the LLM")
    ap.add_argument("--dry-run", action="store_true", help="don't persist state")
    ap.add_argument("--stats", action="store_true", help="show pipeline stats and exit")
    ap.add_argument("-n", type=int, default=None, help="override queue size")
    args = ap.parse_args()

    cfg = load_config()
    conn = db_connect()

    if args.stats:
        show_stats(conn)
        return 0

    limit = args.n or cfg["targets"].get("per_day", 10)
    cooldown = cfg["targets"].get("company_cooldown_days", 30)

    profile_text = load_profile_text(conn)
    pool = max(limit, cfg.get("resume", {}).get("shortlist", 30)) if profile_text else limit
    candidates = select_queue(conn, collect_jobs(cfg), cfg, pool, cooldown)
    if profile_text:
        candidates = rerank_with_resume(candidates, profile_text, cfg)
    queue = candidates[:limit]

    links = {j.uid: build_links(j, cfg) for j in queue}
    notes: dict[str, str] = {}
    if args.notes:
        for j in queue:
            note = draft_note(j, cfg)
            if note:
                notes[j.uid] = note
            else:
                print(f"[warn] note drafting failed for {j.company} "
                      "(is the LLM backend reachable?)", file=sys.stderr)
                break

    output = render(queue, links, notes)
    print(output)

    if not args.dry_run and queue:
        save_queue(conn, queue, notes)
        OUT_DIR.mkdir(exist_ok=True)
        out_file = OUT_DIR / f"{dt.date.today().isoformat()}.md"
        out_file.write_text(output)
        print(f"\n[saved] {out_file}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
