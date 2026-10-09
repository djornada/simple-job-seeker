"""Pipeline writes: mark a job/company as queued and persist queue items."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from sources import Job

from .postings import archive_posting


def mark_queued(conn: sqlite3.Connection, job: Job) -> None:
    today = dt.date.today().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO seen_jobs (uid, first_seen) VALUES (?, ?)",
        (job.uid, today),
    )
    conn.execute("""
        INSERT INTO queued_companies (company, last_queued)
        VALUES (?, ?)
        ON CONFLICT(company) DO UPDATE SET
            last_queued = excluded.last_queued,
            times_queued = times_queued + 1
    """, (job.company.lower(), today))


def save_item(conn: sqlite3.Connection, job: Job, note: str | None = None) -> None:
    """Persist one queue item for today and archive its posting text. No
    `mark_queued` and no commit: the web build shows items while it's still
    deciding which ones stay (webapp/workers.py)."""
    today = dt.date.today().isoformat()
    archive_posting(conn, job)
    conn.execute("""
        INSERT INTO queue_items
            (date, uid, source, company, title, url, location, score, note,
             description, fit_note, llm_score, flags, fit_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, uid) DO UPDATE SET
            note = COALESCE(queue_items.note, excluded.note),
            fit_note = COALESCE(excluded.fit_note, queue_items.fit_note),
            llm_score = COALESCE(excluded.llm_score, queue_items.llm_score),
            flags = COALESCE(excluded.flags, queue_items.flags),
            fit_json = COALESCE(excluded.fit_json, queue_items.fit_json)
    """, (today, job.uid, job.source, job.company, job.title, job.url,
          job.location, job.score, note,
          job.description, job.fit_note or None, job.llm_score,
          json.dumps(job.flags) if job.flags else None,
          json.dumps(job.fit_detail) if job.fit_detail else None))


def save_queue(conn: sqlite3.Connection, queue: list[Job],
               notes: dict[str, str]) -> None:
    """Persist queue items (feeds the web UI), mark companies queued and
    archive each posting's full text."""
    for j in queue:
        mark_queued(conn, j)
        save_item(conn, j, notes.get(j.uid))
    conn.commit()
