"""Persist a parsed profile into state.db (single row, id = 1)."""
from __future__ import annotations

import datetime as dt
import json
import zipfile

from db import db_connect

from .parse import build_profile


class ProfileError(ValueError):
    """The ZIP opened but held no usable Profile/Positions/Skills data."""


def ingest(source) -> tuple[str, str, list[str]]:
    """Build the profile from a ZIP and store it in state.db.

    `source` is anything zipfile.ZipFile accepts — a path or a seekable
    file-like object (the web UI passes an in-memory upload). Returns
    (text, headline, skills). Raises zipfile.BadZipFile if `source` isn't a
    ZIP, or ProfileError if it holds no usable data.
    """
    with zipfile.ZipFile(source) as zf:
        text, headline, skills = build_profile(zf)
    if not text:
        raise ProfileError(
            "no Profile/Positions/Skills data found in the export "
            "(is this the LinkedIn 'Get a copy of your data' ZIP?)")
    conn = db_connect()
    conn.execute("DELETE FROM profile")
    conn.execute(
        "INSERT INTO profile (id, text, headline, skills_json, imported_at) "
        "VALUES (1, ?, ?, ?, ?)",
        (text, headline, json.dumps(skills),
         dt.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return text, headline, skills
