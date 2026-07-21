"""Command-line interface: import a LinkedIn export ZIP, or show the profile."""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile

from db import db_connect

from .ingest import ProfileError, ingest


def cmd_import(args: argparse.Namespace) -> int:
    path = os.path.expanduser(args.zip)
    try:
        text, headline, skills = ingest(path)
    except FileNotFoundError:
        print(f"[error] no such file: {path}", file=sys.stderr)
        return 1
    except zipfile.BadZipFile:
        print(f"[error] not a ZIP archive: {path}", file=sys.stderr)
        return 1
    except ProfileError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 1
    print(f"[ok] imported profile — {len(text)} chars, {len(skills)} skills"
          f"{f', headline: {headline}' if headline else ''}")
    return 0


def cmd_show(_: argparse.Namespace) -> int:
    conn = db_connect()
    row = conn.execute(
        "SELECT text, headline, skills_json, imported_at "
        "FROM profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        print("No profile imported yet. Run: "
              "python -m profile import <export.zip>")
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
