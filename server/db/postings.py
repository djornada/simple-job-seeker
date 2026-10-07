"""Posting archive: the full text of every queued job, as first seen.

`db_connect` runs `POSTINGS_SCHEMA`; `archive_posting` is called by
`save_queue` for every job it persists. INSERT OR IGNORE, so the first
snapshot wins and a later build or re-rating never overwrites it.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from sources import Job

POSTINGS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS postings (
        uid         TEXT PRIMARY KEY,   -- same key as queue_items.uid
        source      TEXT NOT NULL,
        url         TEXT NOT NULL,
        company     TEXT NOT NULL,
        title       TEXT NOT NULL,
        location    TEXT NOT NULL DEFAULT '',
        text        TEXT NOT NULL,      -- full_text, else description
        archived_at TEXT NOT NULL,
        checked_at  TEXT,               -- liveness re-check (expiry port)
        expired_at  TEXT
    );
"""


def archive_posting(conn: sqlite3.Connection, job: Job) -> None:
    """Snapshot the job's text. Skips jobs with no text (e.g. an extension
    list card), so a later rating that carries the text still lands."""
    text = job.full_text or job.description
    if not text:
        return
    conn.execute("""
        INSERT OR IGNORE INTO postings
            (uid, source, url, company, title, location, text, archived_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (job.uid, job.source, job.url, job.company, job.title,
          job.location, text, dt.datetime.now().isoformat(timespec="seconds")))
