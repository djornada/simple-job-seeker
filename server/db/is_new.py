"""Dedup gate: has this job been seen, or the company queued too recently."""
from __future__ import annotations

import datetime as dt
import sqlite3

from sources import Job


def is_new(conn: sqlite3.Connection, job: Job, cooldown_days: int) -> bool:
    cur = conn.execute("SELECT 1 FROM seen_jobs WHERE uid = ?", (job.uid,))
    if cur.fetchone():
        return False
    cur = conn.execute(
        "SELECT last_queued FROM queued_companies WHERE company = ?",
        (job.company.lower(),),
    )
    row = cur.fetchone()
    if row:
        last = dt.date.fromisoformat(row[0])
        if (dt.date.today() - last).days < cooldown_days:
            return False
    return True
