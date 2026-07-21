#!/usr/bin/env python3
"""
Daily LinkedIn target queue builder.

Fetches remote job boards (RemoteOK, Remotive, We Work Remotely), filters
roles that match your profile, deduplicates against a local SQLite state,
and emits a daily queue of companies with prebuilt LinkedIn search links.

You do the clicking. The script does the deciding.

This module is the entrypoint + facade: the stages live in the pipeline/
package (scoring, select, resume, links, render, over llm/ and db/) and are
re-exported here so `qa.*` keeps working for the web UI.

Usage:
    python queue_agent.py              # build today's queue
    python queue_agent.py --notes      # also draft connection notes via the LLM
    python queue_agent.py --dry-run    # don't persist state
    python queue_agent.py --stats      # show pipeline stats
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys

from db import db_connect, is_new, mark_queued, save_queue  # noqa: F401 — re-exported as qa.*
from pipeline import (  # noqa: F401 — re-exported as qa.*
    build_links,
    draft_note,
    load_profile_bits,
    load_profile_text,
    render,
    rerank_with_resume,
    score_job,
    select_queue,
    show_stats,
)
from sources import Job, collect_jobs
from utils import DB_PATH, OUT_DIR, load_config  # noqa: F401 — DB_PATH re-exported as qa.*


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
