"""Applications: one row per company + role, a status lifecycle, and the
stale rules that surface the ones gone quiet.

`outreach_connect` runs `APPLICATIONS_SCHEMA`. Every change also appends an
outreach event (status as `action`), so the board, history, /company and
/stats see it without knowing this table exists. Shared by tracker.py and
webapp/ (the /applications page, the queue card's "I applied" button and
/due's gone-quiet section). Expects a sqlite3.Row connection (both
`outreach_connect` and `connect` are). Nothing here sends anything on
your behalf.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

APPLICATIONS_SCHEMA = """
    CREATE TABLE IF NOT EXISTS applications (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        company        TEXT NOT NULL,          -- lower-cased, as in outreach
        role           TEXT NOT NULL,
        uid            TEXT,                   -- queue item / posting, when known
        url            TEXT,
        status         TEXT NOT NULL,
        applied_on     TEXT NOT NULL,
        last_activity  TEXT NOT NULL,          -- drives staleness
        followups_sent INTEGER NOT NULL DEFAULT 0,
        note           TEXT,
        UNIQUE (company, role)
    );
"""

OPEN = ("applied", "interview", "offer")
FINAL = ("hired", "rejected", "no_response", "withdrawn", "declined")
STATUSES = OPEN + FINAL

DEFAULTS = {"followup_after_days": 10, "max_followups": 2,
            "no_response_after_days": 60}


class TransitionError(ValueError):
    """A change the lifecycle doesn't allow (or an unknown id)."""


def rules(cfg: dict) -> dict:
    """`[applications]` from config.toml over the defaults."""
    return {**DEFAULTS, **cfg.get("applications", {})}


def allowed_moves(status: str) -> list[str]:
    """Statuses reachable without --force: later open ones, or any final."""
    if status not in OPEN:
        return []
    return list(OPEN[OPEN.index(status) + 1:]) + list(FINAL)


def quiet_days(row: sqlite3.Row) -> int:
    return (dt.date.today() - dt.date.fromisoformat(row["last_activity"])).days


def get(conn: sqlite3.Connection, app_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM applications WHERE id = ?",
                       (app_id,)).fetchone()
    if row is None:
        raise TransitionError(f"no application #{app_id}")
    return row


def _log(conn: sqlite3.Connection, company: str, action: str, note: str) -> None:
    conn.execute(
        "INSERT INTO outreach (company, action, note, date) VALUES (?, ?, ?, ?)",
        (company, action, note, dt.date.today().isoformat()))


def apply(conn: sqlite3.Connection, company: str, role: str, *,
          url: str | None = None, uid: str | None = None,
          note: str | None = None) -> tuple[int, bool]:
    """Track a new application as `applied`. Returns (id, created); an
    existing company + role pair comes back as-is, never duplicated."""
    company, role = company.lower().strip(), role.strip()
    row = conn.execute(
        "SELECT id FROM applications WHERE company = ? AND role = ?",
        (company, role)).fetchone()
    if row is not None:
        return row[0], False
    today = dt.date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO applications (company, role, uid, url, status, "
        "applied_on, last_activity, note) VALUES (?, ?, ?, ?, 'applied', ?, ?, ?)",
        (company, role, uid, url, today, today, note))
    _log(conn, company, "applied", f"{role} — {note}" if note else role)
    conn.commit()
    return cur.lastrowid, True


def move(conn: sqlite3.Connection, app_id: int, status: str, *,
         note: str | None = None, force: bool = False) -> sqlite3.Row:
    """Change status. Open statuses only move forward and a final one is
    never reopened, unless `force`. Raises TransitionError otherwise."""
    row = get(conn, app_id)
    if status not in STATUSES:
        raise TransitionError(f"unknown status '{status}' "
                              f"(one of: {', '.join(STATUSES)})")
    if status == row["status"]:
        raise TransitionError(f"#{app_id} is already {status}")
    if not force and status not in allowed_moves(row["status"]):
        why = ("it's final; reopen with --force" if row["status"] in FINAL
               else "open statuses don't move backwards")
        raise TransitionError(f"#{app_id} is {row['status']}: {why}")
    conn.execute(
        "UPDATE applications SET status = ?, last_activity = ? WHERE id = ?",
        (status, dt.date.today().isoformat(), app_id))
    _log(conn, row["company"], status,
         f"{row['role']} — {note}" if note else row["role"])
    conn.commit()
    return get(conn, app_id)


def record_followup(conn: sqlite3.Connection, app_id: int) -> sqlite3.Row:
    """You followed up (by hand): bump the counter and reset the quiet clock."""
    row = get(conn, app_id)
    if row["status"] not in OPEN:
        raise TransitionError(f"#{app_id} is {row['status']}; follow-ups "
                              "are for open applications")
    conn.execute(
        "UPDATE applications SET followups_sent = followups_sent + 1, "
        "last_activity = ? WHERE id = ?",
        (dt.date.today().isoformat(), app_id))
    _log(conn, row["company"], "messaged", f"follow-up — {row['role']}")
    conn.commit()
    return get(conn, app_id)


def list_apps(conn: sqlite3.Connection, include_final: bool = True
              ) -> list[sqlite3.Row]:
    statuses = STATUSES if include_final else OPEN
    marks = ",".join("?" * len(statuses))
    return conn.execute(
        f"SELECT * FROM applications WHERE status IN ({marks}) "
        "ORDER BY last_activity, id", statuses).fetchall()


def stale(conn: sqlite3.Connection, cfg: dict) -> list[sqlite3.Row]:
    """Open applications quiet long enough to follow up, until
    `max_followups` have been sent."""
    r = rules(cfg)
    return [a for a in list_apps(conn, include_final=False)
            if quiet_days(a) >= r["followup_after_days"]
            and a["followups_sent"] < r["max_followups"]]


def sweep_candidates(conn: sqlite3.Connection, cfg: dict) -> list[sqlite3.Row]:
    """Open applications quiet for `no_response_after_days` or more."""
    days = rules(cfg)["no_response_after_days"]
    return [a for a in list_apps(conn, include_final=False)
            if quiet_days(a) >= days]


def sweep(conn: sqlite3.Connection, cfg: dict, ids: list[int]) -> list[int]:
    """Move the confirmed `ids` to no_response. Only ids that are still
    candidates move, so a stale confirmation can't close a live one."""
    moved = []
    for a in sweep_candidates(conn, cfg):
        if a["id"] in ids:
            move(conn, a["id"], "no_response",
                 note=f"no response after {quiet_days(a)} days")
            moved.append(a["id"])
    return moved
