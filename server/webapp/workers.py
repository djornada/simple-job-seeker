"""Background workers, run in daemon threads: build the queue, draft a
note, check a posting's keyword coverage.

The build persists to queue_items only — the web UI reads from the DB; the
markdown file in queues/ is a CLI artifact.
"""
from __future__ import annotations

import json

from db import db_connect, save_queue
from pipeline import build_queue, check_coverage, draft_note, load_profile_text
from sources import Job
from utils import load_config

from .state import (
    BUILD,
    BUILD_LOCK,
    COVERAGE_FAILED,
    COVERAGE_LOCK,
    COVERAGE_PENDING,
    NOTES_FAILED,
    NOTES_LOCK,
    NOTES_PENDING,
    db,
)


def _build_progress(text: str) -> None:
    with BUILD_LOCK:
        BUILD["progress"] = text


def build_worker(with_notes: bool) -> None:
    try:
        cfg = load_config()
        conn = db_connect()
        limit = cfg["targets"].get("per_day", 30)
        queue = build_queue(conn, cfg, limit, on_progress=lambda done, total:
                            _build_progress(f"scoring fit {done}/{total}"))
        notes: dict[str, str] = {}
        if with_notes:
            for i, j in enumerate(queue, 1):
                _build_progress(f"drafting notes {i}/{len(queue)}")
                note = draft_note(j, cfg)
                if note:
                    notes[j.uid] = note
        if queue:
            save_queue(conn, queue, notes)
        conn.close()
        error = ""
    except Exception as e:  # noqa: BLE001 — surface any failure in the UI
        error = str(e) or e.__class__.__name__
    with BUILD_LOCK:
        BUILD["running"] = False
        BUILD["error"] = error
        BUILD["progress"] = ""


def note_worker(date: str, uid: str) -> None:
    note = None
    try:
        cfg = load_config()
        conn = db()
        row = conn.execute(
            "SELECT source, title, company, url, location FROM queue_items "
            "WHERE date = ? AND uid = ?", (date, uid)).fetchone()
        if row:
            job = Job(source=row["source"], title=row["title"],
                     company=row["company"], url=row["url"],
                     location=row["location"])
            note = draft_note(job, cfg)
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


def coverage_worker(date: str, uid: str) -> None:
    """Check the archived posting's keywords against the profile and store
    the result in `queue_items.coverage_json`."""
    error = "check failed (see the server log)"
    try:
        cfg = load_config()
        conn = db()
        posting = conn.execute(
            "SELECT text FROM postings WHERE uid = ?", (uid,)).fetchone()
        profile_text = load_profile_text(conn)
        if posting is None:
            error = "no saved posting to read"
        elif not profile_text:
            error = "no résumé imported"
        else:
            result = check_coverage(posting["text"], profile_text, cfg)
            if result:
                conn.execute(
                    "UPDATE queue_items SET coverage_json = ? "
                    "WHERE date = ? AND uid = ?",
                    (json.dumps(result), date, uid))
                conn.commit()
                error = ""
            elif result is None:
                error = ("LLM unreachable or rate-limited "
                         "(check the server log)")
            else:
                error = "the model's reply had no usable keywords"
        conn.close()
    finally:
        with COVERAGE_LOCK:
            COVERAGE_PENDING.discard(uid)
            if error:
                COVERAGE_FAILED[uid] = error
            else:
                COVERAGE_FAILED.pop(uid, None)
