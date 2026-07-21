"""Shared web-app primitives.

The DB handle and HTML-escape helper, plus the background-build state guarded
by locks — mutated by workers, read by pages and POST handlers. Everyone
imports the same lock/dict/set objects, so mutations are shared.
"""
from __future__ import annotations

import html
import re
import sqlite3
import threading

import queue_agent as qa

BUILD = {"running": False, "error": ""}
BUILD_LOCK = threading.Lock()
NOTES_PENDING: set[str] = set()          # queue item uids with a note in flight
NOTES_FAILED: set[str] = set()           # uids whose last draft attempt failed
NOTES_LOCK = threading.Lock()

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(qa.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)
