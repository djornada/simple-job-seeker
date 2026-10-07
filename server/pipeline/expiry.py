"""Expired-posting check: re-visit archived postings, mark the dead ones.

`recheck(conn, cfg)` picks postings that aren't expired, were archived at
least `min_age_days` ago and weren't checked in the last `recheck_days`,
least recently checked first, up to `max_checks`, and asks the source's
`LIVENESS` checker about each, one second apart. False marks `expired_at`;
True or None ("can't tell") only records `checked_at`. LinkedIn is never
touched: its sources aren't in LIVENESS, the checkers refuse its hosts,
and this module skips them before calling a checker at all.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import time

from sources import LIVENESS, is_linkedin

DEFAULTS = {"max_checks": 50, "min_age_days": 2, "recheck_days": 3}


def rules(cfg: dict) -> dict:
    """`[expiry]` from config.toml over the defaults."""
    return {**DEFAULTS, **cfg.get("expiry", {})}


def _stamp(days_ago: float = 0) -> str:
    when = dt.datetime.now() - dt.timedelta(days=days_ago)
    return when.isoformat(timespec="seconds")


def candidates(conn: sqlite3.Connection, cfg: dict) -> list[tuple]:
    """(uid, source, url, company, title) rows due a check, never-checked
    first, then least recently checked."""
    r = rules(cfg)
    sources = sorted(LIVENESS)
    marks = ",".join("?" * len(sources))
    return conn.execute(
        "SELECT uid, source, url, company, title FROM postings "
        "WHERE expired_at IS NULL AND archived_at <= ? "
        "AND (checked_at IS NULL OR checked_at <= ?) "
        f"AND source IN ({marks}) "
        "ORDER BY checked_at, archived_at LIMIT ?",
        (_stamp(r["min_age_days"]), _stamp(r["recheck_days"]), *sources,
         int(r["max_checks"]))).fetchall()


def recheck(conn: sqlite3.Connection, cfg: dict,
            sleep=time.sleep) -> dict[str, list[tuple]]:
    """Check each candidate; returns the rows grouped by verdict
    ("expired", "live", "unknown")."""
    out: dict[str, list[tuple]] = {"expired": [], "live": [], "unknown": []}
    for i, row in enumerate(candidates(conn, cfg)):
        uid, source, url = row[0], row[1], row[2]
        if i:
            sleep(1)  # be polite to the boards
        verdict = None if is_linkedin(url) else LIVENESS[source](url)
        now = _stamp()
        conn.execute(
            "UPDATE postings SET checked_at = ?, "
            "expired_at = CASE WHEN ? THEN ? ELSE expired_at END WHERE uid = ?",
            (now, verdict is False, now, uid))
        conn.commit()
        key = {False: "expired", True: "live"}.get(verdict, "unknown")
        out[key].append(row)
    return out
