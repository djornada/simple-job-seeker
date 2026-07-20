"""SQLite state layer, one function per module (mirrors sources/).

`db_connect` owns the pipeline schema (seen_jobs, queued_companies,
queue_items, profile) plus lazy ALTERs; `is_new` is the dedup + company
cooldown gate. tracker.py keeps its own outreach schema on the same
state.db; both use CREATE TABLE IF NOT EXISTS. queue_agent re-exports these
so `qa.db_connect` / `qa.is_new` keep working.
"""
from __future__ import annotations

from .db_connect import db_connect
from .is_new import is_new

__all__ = ["db_connect", "is_new"]
