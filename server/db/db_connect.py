"""Connection + schema: owns the pipeline tables on the shared state.db."""
from __future__ import annotations

import sqlite3

from utils import DB_PATH

from .postings import POSTINGS_SCHEMA


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            uid TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS queued_companies (
            company TEXT PRIMARY KEY,
            last_queued TEXT NOT NULL,
            times_queued INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS queue_items (
            date TEXT NOT NULL,
            uid TEXT NOT NULL,
            source TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            note TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            fit_note TEXT,
            llm_score REAL,
            PRIMARY KEY (date, uid)
        );
        CREATE TABLE IF NOT EXISTS profile (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            text        TEXT NOT NULL,
            headline    TEXT,
            skills_json TEXT,
            imported_at TEXT
        );
    """)
    conn.executescript(POSTINGS_SCHEMA)
    for col in ("description TEXT", "fit_note TEXT", "llm_score REAL"):
        try:
            conn.execute(f"ALTER TABLE queue_items ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass  # column already exists
    return conn
