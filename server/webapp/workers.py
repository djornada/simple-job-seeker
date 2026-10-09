"""Background workers, run in daemon threads: build the queue, draft a
note, check a posting's keyword coverage.

The build persists to queue_items only — the web UI reads from the DB; the
markdown file in queues/ is a CLI artifact. It writes cards as fit scoring
goes (`_Stream`), so the queue page can show them before the build ends.
"""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from db import db_connect, mark_queued, save_item
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


class _Stream:
    """Today's cards while a build runs. After each fit judgment, `judged`
    syncs queue_items to the best `limit` jobs so far above
    `[resume].min_llm_score` — the order `rerank_with_resume` ends with —
    so a card shows as soon as its job makes the cut and goes if a better
    one pushes it out. A card someone has touched stays. `finish` syncs to
    the final queue and only then calls `mark_queued`, so a card that came
    and went leaves no company cooldown behind."""

    def __init__(self, conn: sqlite3.Connection, cfg: dict, limit: int,
                 with_notes: bool) -> None:
        self.conn, self.limit, self.with_notes = conn, limit, with_notes
        self.floor = cfg.get("resume", {}).get("min_llm_score", 5)
        self.date = dt.date.today().isoformat()
        self.passed: list[Job] = []    # judged jobs above the floor, best first
        self.shown: dict[str, Job] = {}  # uid → job, for this build's cards
        self.to_draft: set[str] = set()  # cards showing "drafting note…"

    def judged(self, job: Job) -> None:
        if (job.llm_score or 0) >= self.floor:
            self.passed.append(job)
            self.passed.sort(key=lambda j: (j.llm_score or 0, j.score),
                             reverse=True)
        self.sync(self.passed[:self.limit])

    def sync(self, want: list[Job]) -> None:
        for j in want:
            if j.uid not in self.shown:
                if self.with_notes:  # pending before the card can render
                    with NOTES_LOCK:
                        NOTES_PENDING.add(j.uid)
                    self.to_draft.add(j.uid)
                save_item(self.conn, j)
                self.shown[j.uid] = j
        keep = {j.uid for j in want}
        for uid in [u for u in self.shown if u not in keep]:
            if not self._touched(uid):
                self.conn.execute(
                    "DELETE FROM queue_items WHERE date = ? AND uid = ?",
                    (self.date, uid))
                self._forget(uid)
        self.conn.commit()

    def _touched(self, uid: str) -> bool:
        """Ticked, noted, keyword-checked or applied to, or a check or a
        draft you asked for still running."""
        row = self.conn.execute(
            "SELECT done OR note IS NOT NULL OR coverage_json IS NOT NULL "
            "OR EXISTS(SELECT 1 FROM applications a WHERE a.uid = q.uid) "
            "FROM queue_items q WHERE date = ? AND uid = ?",
            (self.date, uid)).fetchone()
        with COVERAGE_LOCK:
            checking = uid in COVERAGE_PENDING
        with NOTES_LOCK:
            drafting = uid in NOTES_PENDING and not self.with_notes
        return bool(row and row[0]) or checking or drafting

    def _forget(self, uid: str) -> None:
        del self.shown[uid]
        if uid in self.to_draft:
            self.to_draft.discard(uid)
            with NOTES_LOCK:
                NOTES_PENDING.discard(uid)

    def finish(self, queue: list[Job]) -> None:
        """Sync to the final queue, then mark every card left as queued."""
        self.sync(queue)
        self.settle()

    def settle(self) -> None:
        """Mark this build's cards queued (also after a failure: they're on
        the page, so they count)."""
        for j in self.shown.values():
            mark_queued(self.conn, j)
        self.conn.commit()

    def cards(self) -> list[str]:
        """This build's cards, best first."""
        return [j.uid for j in sorted(
            self.shown.values(), key=lambda j: (j.llm_score or 0, j.score),
            reverse=True)]


def build_worker(with_notes: bool) -> None:
    stream = None
    try:
        cfg = load_config()
        conn = db_connect()
        limit = cfg["targets"].get("per_day", 30)
        stream = _Stream(conn, cfg, limit, with_notes)
        queue = build_queue(conn, cfg, limit, on_progress=lambda done, total:
                            _build_progress(f"scoring fit {done}/{total}"),
                            on_judged=stream.judged)
        stream.finish(queue)
        # the cards are up, each showing "drafting note…" if notes were asked
        uids = [u for u in stream.cards() if u in stream.to_draft]
        for i, uid in enumerate(uids, 1):
            _build_progress(f"drafting notes {i}/{len(uids)}")
            stream.to_draft.discard(uid)
            try:
                note_worker(stream.date, uid)
            except Exception:  # noqa: BLE001,S110 — marked failed on the card
                pass
        conn.close()
        error = ""
    except Exception as e:  # noqa: BLE001 — surface any failure in the UI
        error = str(e) or e.__class__.__name__
        if stream is not None:
            try:
                stream.settle()
            except sqlite3.Error:
                pass
    if stream is not None and stream.to_draft:  # a failure left some pending
        with NOTES_LOCK:
            NOTES_PENDING.difference_update(stream.to_draft)
    with BUILD_LOCK:
        BUILD["running"] = False
        BUILD["error"] = error
        BUILD["progress"] = ""


def note_worker(date: str, uid: str) -> None:
    note = None
    try:
        cfg = load_config()
        conn = db()
        # the archived posting, if any, trimmed like a source's description
        # (the slice the LLM saw at build time) so the note can match it
        row = conn.execute(
            "SELECT q.source, q.title, q.company, q.url, q.location, "
            "substr(p.text, 1, 2000) AS posting FROM queue_items q "
            "LEFT JOIN postings p ON p.uid = q.uid "
            "WHERE q.date = ? AND q.uid = ?", (date, uid)).fetchone()
        if row:
            job = Job(source=row["source"], title=row["title"],
                     company=row["company"], url=row["url"],
                     location=row["location"],
                     description=row["posting"] or "")
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
