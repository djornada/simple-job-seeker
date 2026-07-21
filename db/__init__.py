"""SQLite state layer, one concern per module (mirrors sources/).

`db_connect` owns the pipeline schema (seen_jobs, queued_companies,
queue_items, profile) plus lazy ALTERs; `is_new` is the dedup + company
cooldown gate; `queue` holds the pipeline writes (`mark_queued`,
`save_queue`); `outreach_connect` owns the tracker's outreach schema on the
same state.db; `connect` is the schema-less Row-factory handle for
request-serving code. All schemas use CREATE TABLE IF NOT EXISTS, so
creation order doesn't matter. queue_agent.py and webapp/ both import
straight from this package.
"""
from __future__ import annotations

from .connect import connect
from .db_connect import db_connect
from .is_new import is_new
from .outreach import outreach_connect
from .queue import mark_queued, save_queue

__all__ = ["connect", "db_connect", "is_new", "mark_queued",
           "outreach_connect", "save_queue"]
