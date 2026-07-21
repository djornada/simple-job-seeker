#!/usr/bin/env python3
"""
Outreach tracker. Shares state.db with queue_agent.py.

Log every touchpoint, never lose a follow-up.

Usage:
    tracker.py add <company> [--person NAME] [--action A] [--note TEXT] [--followup DAYS]
    tracker.py due                     # follow-ups due or overdue
    tracker.py done <id>               # close a follow-up
    tracker.py board                   # pipeline overview by latest stage
    tracker.py history <company>       # full timeline for one company

Actions: visited, connected, messaged, replied, meeting, applied, rejected, offer

Examples:
    tracker.py add "Acme Corp" --person "Jane Doe" --action connected --followup 5
    tracker.py add Acme --action replied --note "asked for my CV" --followup 2
    tracker.py due
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys

from db import outreach_connect as db_connect

ACTIONS = ["visited", "connected", "messaged", "replied",
           "meeting", "applied", "rejected", "offer"]

# stage weight for the board (higher = further down the funnel)
STAGE_ORDER = {a: i for i, a in enumerate(ACTIONS)}


def resolve_company(conn: sqlite3.Connection, name: str) -> str:
    """Allow prefixes: 'acme' resolves to 'acme corp' if unambiguous."""
    key = name.lower().strip()
    rows = conn.execute(
        "SELECT DISTINCT company FROM outreach WHERE company LIKE ? "
        "UNION SELECT company FROM queued_companies WHERE company LIKE ?",
        (f"{key}%", f"{key}%"),
    ).fetchall()
    matches = sorted({r[0] for r in rows})
    if len(matches) == 1:
        return matches[0]
    if key in matches:
        return key
    if len(matches) > 1:
        print(f"[warn] '{name}' is ambiguous: {', '.join(matches)} — using exact input",
              file=sys.stderr)
    return key


def cmd_add(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    company = resolve_company(conn, args.company)
    today = dt.date.today()
    due = (today + dt.timedelta(days=args.followup)).isoformat() \
        if args.followup is not None else None
    conn.execute(
        "INSERT INTO outreach (company, person, action, note, date, followup_due) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (company, args.person, args.action, args.note, today.isoformat(), due),
    )
    conn.commit()
    msg = f"[ok] {company} · {args.action}"
    if args.person:
        msg += f" · {args.person}"
    if due:
        msg += f" · follow-up {due}"
    print(msg)


def cmd_due(conn: sqlite3.Connection, _: argparse.Namespace) -> None:
    today = dt.date.today().isoformat()
    rows = conn.execute(
        "SELECT id, company, person, action, note, followup_due FROM outreach "
        "WHERE followup_due IS NOT NULL AND followup_done = 0 AND followup_due <= ? "
        "ORDER BY followup_due",
        (today,),
    ).fetchall()
    if not rows:
        print("Nothing due. Go write a post instead.")
        return
    for r in rows:
        overdue = " (OVERDUE)" if r["followup_due"] < today else ""
        person = f" · {r['person']}" if r["person"] else ""
        note = f" — {r['note']}" if r["note"] else ""
        print(f"#{r['id']:<4} {r['followup_due']}{overdue}  {r['company']}{person} "
              f"[last: {r['action']}]{note}")


def cmd_done(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    cur = conn.execute(
        "UPDATE outreach SET followup_done = 1 WHERE id = ?", (args.id,))
    conn.commit()
    print(f"[ok] follow-up #{args.id} closed" if cur.rowcount
          else f"[warn] no follow-up with id {args.id}")


def cmd_board(conn: sqlite3.Connection, _: argparse.Namespace) -> None:
    rows = conn.execute(
        "SELECT company, action, date FROM outreach ORDER BY date, id").fetchall()
    latest: dict[str, sqlite3.Row] = {r["company"]: r for r in rows}
    if not latest:
        print("No outreach logged yet. Start with: tracker.py add <company> --action visited")
        return
    by_stage: dict[str, list[tuple[str, str]]] = {}
    for company, r in latest.items():
        by_stage.setdefault(r["action"], []).append((company, r["date"]))
    for action in sorted(by_stage, key=lambda a: -STAGE_ORDER.get(a, 0)):
        print(f"\n{action.upper()} ({len(by_stage[action])})")
        for company, date in sorted(by_stage[action], key=lambda x: x[1], reverse=True):
            print(f"  {date}  {company}")


def cmd_history(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    company = resolve_company(conn, args.company)
    rows = conn.execute(
        "SELECT date, action, person, note, followup_due, followup_done "
        "FROM outreach WHERE company = ? ORDER BY date, id",
        (company,),
    ).fetchall()
    if not rows:
        print(f"No history for '{company}'.")
        return
    print(f"{company}")
    for r in rows:
        person = f" · {r['person']}" if r["person"] else ""
        note = f" — {r['note']}" if r["note"] else ""
        fu = ""
        if r["followup_due"]:
            fu = f"  [follow-up {r['followup_due']}{'' if r['followup_done'] else ' pending'}]"
        print(f"  {r['date']}  {r['action']}{person}{note}{fu}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Track LinkedIn outreach.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="log an interaction")
    p.add_argument("company")
    p.add_argument("--person", help="who you talked to")
    p.add_argument("--action", choices=ACTIONS, default="visited")
    p.add_argument("--note")
    p.add_argument("--followup", type=int, metavar="DAYS",
                   help="schedule a follow-up in N days")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("due", help="follow-ups due or overdue")
    p.set_defaults(fn=cmd_due)

    p = sub.add_parser("done", help="close a follow-up by id")
    p.add_argument("id", type=int)
    p.set_defaults(fn=cmd_done)

    p = sub.add_parser("board", help="pipeline overview")
    p.set_defaults(fn=cmd_board)

    p = sub.add_parser("history", help="timeline for one company")
    p.add_argument("company")
    p.set_defaults(fn=cmd_history)

    args = ap.parse_args()
    conn = db_connect()
    args.fn(conn, args)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
