"""SQLite state layer, one concern per module (mirrors sources/).

`db_connect` owns the pipeline schema (seen_jobs, queued_companies,
queue_items, profile) plus lazy ALTERs; `is_new` is the dedup + company
cooldown gate; `queue` holds the pipeline writes (`mark_queued`,
`save_queue`). tracker.py keeps its own outreach schema on the same
state.db; both use CREATE TABLE IF NOT EXISTS. queue_agent re-exports these
so `qa.db_connect` / `qa.is_new` / `qa.save_queue` keep working.
"""
from __future__ import annotations

from .db_connect import db_connect
from .is_new import is_new
from .queue import mark_queued, save_queue

__all__ = ["db_connect", "is_new", "mark_queued", "save_queue"]
