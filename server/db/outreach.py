"""Outreach connection + schema, on the same shared state.db.

Used by the tracker CLI and the web UI. Also ensures the applications
table (`db/applications.py`). Row factory is sqlite3.Row because
every consumer reads columns by name.
"""
from __future__ import annotations

import sqlite3

from utils import DB_PATH

from .applications import APPLICATIONS_SCHEMA


def outreach_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS outreach (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            person TEXT,
            action TEXT NOT NULL,
            note TEXT,
            date TEXT NOT NULL,
            followup_due TEXT,
            followup_done INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_outreach_company ON outreach(company);
        -- shared with the pipeline; created here too so either tool can run first
        CREATE TABLE IF NOT EXISTS queued_companies (
            company TEXT PRIMARY KEY,
            last_queued TEXT NOT NULL,
            times_queued INTEGER NOT NULL DEFAULT 1
        );
    """)
    conn.executescript(APPLICATIONS_SCHEMA)
    return conn
