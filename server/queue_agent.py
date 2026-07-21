#!/usr/bin/env python3
"""
Daily LinkedIn target queue builder.

Fetches remote job boards (RemoteOK, Remotive, We Work Remotely), filters
roles that match your profile, deduplicates against a local SQLite state,
and emits a daily queue of companies with prebuilt LinkedIn search links.

You do the clicking. The script does the deciding.

This module is the CLI entrypoint: the stages live in the pipeline/ package
(scoring, select, resume, links, render, over llm/ and db/); the web UI
imports them directly rather than through this module.

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

from db import db_connect, save_queue
from pipeline import build_links, build_queue, draft_note, render, show_stats
from utils import OUT_DIR, load_config


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
    queue = build_queue(conn, cfg, limit)

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
