#!/usr/bin/env python3
"""
Resume ingestion for the queue agent.

Feeds your real experience into job scoring and connection notes, sourced
from the LinkedIn data export ZIP (Settings → Get a copy of your data).
Nothing touches LinkedIn programmatically: you download the ZIP by hand,
this only reads it from local disk. The profile lands in state.db, which is
already gitignored.

Usage:
    python profile.py import ~/Downloads/LinkedInDataExport.zip
    python profile.py show
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import os
import sys
import zipfile

import queue_agent as qa

PROFILE_CHARS = 1500     # compact profile text budget for the LLM re-rank


# --------------------------------------------------------------------------- #
# ZIP / CSV reading (export layouts vary — match by basename & header name)
# --------------------------------------------------------------------------- #

def _find_member(zf: zipfile.ZipFile, basename: str) -> str | None:
    want = basename.lower()
    for name in zf.namelist():
        if name.rsplit("/", 1)[-1].lower() == want:
            return name
    return None


def _read_csv(zf: zipfile.ZipFile, basename: str) -> list[dict]:
    name = _find_member(zf, basename)
    if not name:
        return []
    with zf.open(name) as f:
        text = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
        return list(csv.DictReader(text))


def _field(row: dict, *names: str) -> str:
    """Case-insensitive header lookup; returns the first non-empty match."""
    lower = {(k or "").strip().lower(): v for k, v in row.items()}
    for n in names:
        v = (lower.get(n.lower()) or "").strip()
        if v:
            return v
    return ""


# --------------------------------------------------------------------------- #
# Profile assembly
# --------------------------------------------------------------------------- #

def build_profile(zf: zipfile.ZipFile) -> tuple[str, str, list[str]]:
    """Return (compact_text, headline, skills)."""
    profile_rows = _read_csv(zf, "Profile.csv")
    positions = _read_csv(zf, "Positions.csv")
    skills_rows = _read_csv(zf, "Skills.csv")

    headline = summary = ""
    if profile_rows:
        headline = _field(profile_rows[0], "Headline")
        summary = _field(profile_rows[0], "Summary")

    skills = [_field(r, "Name") for r in skills_rows]
    skills = [s for s in skills if s]

    parts: list[str] = []
    if headline:
        parts.append(f"Headline: {headline}")
    if summary:
        parts.append(f"Summary: {summary}")
    if positions:
        parts.append("Experience:")
        for r in positions[:6]:  # most-recent-first in the export
            title = _field(r, "Title")
            company = _field(r, "Company Name")
            started = _field(r, "Started On")
            finished = _field(r, "Finished On") or "Present"
            desc = _field(r, "Description")
            when = f" ({started}–{finished})" if started else ""
            line = f"- {title} @ {company}{when}".rstrip()
            if desc:
                line += f": {desc[:280]}"
            parts.append(line)
    if skills:
        parts.append("Skills: " + ", ".join(skills[:30]))

    return "\n".join(parts)[:PROFILE_CHARS], headline, skills


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

def cmd_import(args: argparse.Namespace) -> int:
    path = os.path.expanduser(args.zip)
    try:
        with zipfile.ZipFile(path) as zf:
            text, headline, skills = build_profile(zf)
    except FileNotFoundError:
        print(f"[error] no such file: {path}", file=sys.stderr)
        return 1
    except zipfile.BadZipFile:
        print(f"[error] not a ZIP archive: {path}", file=sys.stderr)
        return 1

    if not text:
        print("[error] no Profile/Positions/Skills data found in the export "
              "(is this the LinkedIn 'Get a copy of your data' ZIP?)",
              file=sys.stderr)
        return 1

    conn = qa.db_connect()
    conn.execute("DELETE FROM profile")
    conn.execute(
        "INSERT INTO profile (id, text, headline, skills_json, imported_at) "
        "VALUES (1, ?, ?, ?, ?)",
        (text, headline, json.dumps(skills),
         dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    print(f"[ok] imported profile — {len(text)} chars, {len(skills)} skills"
          f"{f', headline: {headline}' if headline else ''}")
    return 0


def cmd_show(_: argparse.Namespace) -> int:
    conn = qa.db_connect()
    row = conn.execute(
        "SELECT text, headline, skills_json, imported_at "
        "FROM profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        print("No profile imported yet. Run: "
              "python profile.py import <export.zip>")
        return 1
    text, headline, skills_json, imported_at = row
    print(f"Imported: {imported_at}")
    if headline:
        print(f"Headline: {headline}")
    skills = json.loads(skills_json) if skills_json else []
    if skills:
        print(f"Skills ({len(skills)}): {', '.join(skills)}")
    print("\n--- profile text ---\n")
    print(text)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Import your LinkedIn resume export.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import", help="ingest a LinkedIn data-export ZIP")
    p.add_argument("zip", help="path to the export ZIP from LinkedIn")
    p.set_defaults(fn=cmd_import)

    p = sub.add_parser("show", help="print the stored profile")
    p.set_defaults(fn=cmd_show)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
