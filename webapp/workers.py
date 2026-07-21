"""Background workers, run in daemon threads: build the queue, draft a note.

The build persists to queue_items only — the web UI reads from the DB; the
markdown file in queues/ is a CLI artifact.
"""
from __future__ import annotations

import queue_agent as qa
from db import db_connect

from .state import (
    BUILD,
    BUILD_LOCK,
    NOTES_FAILED,
    NOTES_LOCK,
    NOTES_PENDING,
    db,
)


def build_worker(with_notes: bool) -> None:
    try:
        cfg = qa.load_config()
        conn = db_connect()
        limit = cfg["targets"].get("per_day", 10)
        cooldown = cfg["targets"].get("company_cooldown_days", 30)
        profile_text = qa.load_profile_text(conn)
        pool = (max(limit, cfg.get("resume", {}).get("shortlist", 30))
                if profile_text else limit)
        candidates = qa.select_queue(conn, qa.collect_jobs(cfg), cfg, pool, cooldown)
        if profile_text:
            candidates = qa.rerank_with_resume(candidates, profile_text, cfg)
        queue = candidates[:limit]
        notes: dict[str, str] = {}
        if with_notes:
            for j in queue:
                note = qa.draft_note(j, cfg)
                if note:
                    notes[j.uid] = note
        if queue:
            qa.save_queue(conn, queue, notes)
        conn.close()
        error = ""
    except Exception as e:  # noqa: BLE001 — surface any failure in the UI
        error = str(e) or e.__class__.__name__
    with BUILD_LOCK:
        BUILD["running"] = False
        BUILD["error"] = error


def note_worker(date: str, uid: str) -> None:
    note = None
    try:
        cfg = qa.load_config()
        conn = db()
        row = conn.execute(
            "SELECT source, title, company, url, location FROM queue_items "
            "WHERE date = ? AND uid = ?", (date, uid)).fetchone()
        if row:
            job = qa.Job(source=row["source"], title=row["title"],
                         company=row["company"], url=row["url"],
                         location=row["location"])
            note = qa.draft_note(job, cfg)
            if note:
                conn.execute(
                    "UPDATE queue_items SET note = ? WHERE date = ? AND uid = ?",
                    (note, date, uid))
                conn.commit()
        conn.close()
        failed = not note  # None = LLM unreachable/rate-limited (see server log)
    except Exception:  # noqa: BLE001 — a crash still counts as a failed draft
        failed = True
        raise
    finally:
        with NOTES_LOCK:
            NOTES_PENDING.discard(uid)
            (NOTES_FAILED.add if failed else NOTES_FAILED.discard)(uid)
