"""Résumé ingestion for the queue agent.

Feeds your real experience into job scoring and connection notes, sourced
from the LinkedIn data export ZIP (Settings → Get a copy of your data).
Nothing touches LinkedIn programmatically: you download the ZIP by hand,
this only reads it from local disk. The profile lands in state.db, which is
already gitignored.

One concern per module (mirrors sources/ and db/): parse.py builds the
profile from the ZIP, ingest.py persists it, cli.py is the command line.
The facade re-exports the reusable bits so `profile.ingest` /
`profile.ProfileError` keep working for the web UI.

CLI:
    python -m profile import ~/Downloads/LinkedInDataExport.zip
    python -m profile show
"""
from .ingest import ProfileError, ingest
from .parse import build_profile

__all__ = ["ingest", "ProfileError", "build_profile"]
