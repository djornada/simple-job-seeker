"""Pipeline writes: mark a job/company as queued and persist queue items."""
from __future__ import annotations

import datetime as dt
import sqlite3

from sources import Job


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


def save_queue(conn: sqlite3.Connection, queue: list[Job],
               notes: dict[str, str]) -> None:
    """Persist queue items (feeds the web UI) and mark companies queued."""
    today = dt.date.today().isoformat()
    for j in queue:
        mark_queued(conn, j)
        conn.execute("""
            INSERT INTO queue_items
                (date, uid, source, company, title, url, location, score, note,
                 description, fit_note, llm_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, uid) DO UPDATE SET
                note = COALESCE(queue_items.note, excluded.note),
                fit_note = COALESCE(excluded.fit_note, queue_items.fit_note),
                llm_score = COALESCE(excluded.llm_score, queue_items.llm_score)
        """, (today, j.uid, j.source, j.company, j.title, j.url,
              j.location, j.score, notes.get(j.uid),
              j.description, j.fit_note or None, j.llm_score))
    conn.commit()
