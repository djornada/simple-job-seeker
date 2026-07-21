"""Bare connection to the shared state.db, rows addressable by name.

No schema creation here — request-serving code uses this light handle and
relies on the schemas existing (`db_connect` / `outreach_connect` are run
once at web-server startup; the CLIs create their own).
"""
from __future__ import annotations

import sqlite3

from utils import DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
