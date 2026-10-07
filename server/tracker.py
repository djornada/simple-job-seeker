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

    tracker.py apply <company> <role> [--url URL] [--note TEXT]
    tracker.py move <id> <status> [--note TEXT] [--force]
    tracker.py followup <id>           # you followed up on an application
    tracker.py apps [--all]            # open applications (--all: finals too)
    tracker.py stale                   # applications due a follow-up
    tracker.py sweep                   # quiet too long -> no_response (asks)

Actions: visited, connected, messaged, replied, meeting, applied, rejected,
offer, interview, no_response, withdrawn, declined, hired

Application statuses: open applied -> interview -> offer (forward only);
final hired, rejected, no_response, withdrawn, declined (reopen: --force).
Every status change is also logged as an outreach action.

Examples:
    tracker.py add "Acme Corp" --person "Jane Doe" --action connected --followup 5
    tracker.py add Acme --action replied --note "asked for my CV" --followup 2
    tracker.py due
    tracker.py apply acme "Senior Frontend Engineer" --url https://...
    tracker.py move 3 interview --note "call with the EM on Tuesday"
"""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys

from db import applications as apps
from db import outreach_connect as db_connect
from utils import load_config

# Append only: STAGE_ORDER weights are list positions (the board's order).
ACTIONS = ["visited", "connected", "messaged", "replied",
           "meeting", "applied", "rejected", "offer",
           "interview", "no_response", "withdrawn", "declined", "hired"]

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


def _app_line(a: sqlite3.Row) -> str:
    return (f"#{a['id']:<4} {a['applied_on']}  {a['company']} · {a['role']}  "
            f"[{a['status']}, quiet {apps.quiet_days(a)}d, "
            f"follow-ups {a['followups_sent']}]")


def cmd_apply(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    company = resolve_company(conn, args.company)
    app_id, created = apps.apply(conn, company, args.role, url=args.url,
                                 note=args.note)
    if created:
        print(f"[ok] #{app_id} {company} · {args.role} · applied")
    else:
        a = apps.get(conn, app_id)
        print(f"[info] already tracked: {_app_line(a)}")


def cmd_move(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    try:
        a = apps.move(conn, args.id, args.status, note=args.note,
                      force=args.force)
    except apps.TransitionError as e:
        print(f"[refused] {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[ok] {_app_line(a)}")


def cmd_followup(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    try:
        a = apps.record_followup(conn, args.id)
    except apps.TransitionError as e:
        print(f"[refused] {e}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[ok] follow-up recorded: {_app_line(a)}")


def cmd_apps(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    rows = apps.list_apps(conn, include_final=args.all)
    if not rows:
        print("No applications tracked. Start with: tracker.py apply <company> <role>")
        return
    for status in tuple(reversed(apps.OPEN)) + apps.FINAL:  # furthest first
        group = [a for a in rows if a["status"] == status]
        if group:
            print(f"\n{status.upper()} ({len(group)})")
            for a in group:
                print(f"  {_app_line(a)}")


def cmd_stale(conn: sqlite3.Connection, _: argparse.Namespace) -> None:
    rows = apps.stale(conn, load_config())
    if not rows:
        print("No application needs a follow-up.")
        return
    for a in rows:
        print(f"{_app_line(a)}\n      follow up, then: tracker.py followup {a['id']}")


def cmd_sweep(conn: sqlite3.Connection, _: argparse.Namespace) -> None:
    cfg = load_config()
    rows = apps.sweep_candidates(conn, cfg)
    days = apps.rules(cfg)["no_response_after_days"]
    if not rows:
        print(f"No open application has been quiet for {days}+ days.")
        return
    print(f"Quiet for {days}+ days:")
    for a in rows:
        print(f"  {_app_line(a)}")
    try:
        answer = input(f"Move {len(rows)} to no_response? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        print("Nothing moved.")
        return
    moved = apps.sweep(conn, cfg, [a["id"] for a in rows])
    print(f"[ok] moved {len(moved)} to no_response")


def main() -> int:
    ap = argparse.ArgumentParser(description="Track LinkedIn outreach and applications.")
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

    p = sub.add_parser("apply", help="track an application")
    p.add_argument("company")
    p.add_argument("role")
    p.add_argument("--url")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_apply)

    p = sub.add_parser("move", help="change an application's status")
    p.add_argument("id", type=int)
    p.add_argument("status", choices=apps.STATUSES)
    p.add_argument("--note")
    p.add_argument("--force", action="store_true",
                   help="allow moving backwards or reopening a final status")
    p.set_defaults(fn=cmd_move)

    p = sub.add_parser("followup", help="record a follow-up you sent")
    p.add_argument("id", type=int)
    p.set_defaults(fn=cmd_followup)

    p = sub.add_parser("apps", help="list applications by status")
    p.add_argument("--all", action="store_true", help="include final statuses")
    p.set_defaults(fn=cmd_apps)

    p = sub.add_parser("stale", help="applications due a follow-up")
    p.set_defaults(fn=cmd_stale)

    p = sub.add_parser("sweep", help="move long-quiet applications to no_response")
    p.set_defaults(fn=cmd_sweep)

    args = ap.parse_args()
    conn = db_connect()
    args.fn(conn, args)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
