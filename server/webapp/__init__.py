"""Local web UI for the daily queue + outreach tracker.

Same principle as the CLIs: nothing touches LinkedIn programmatically.
The app renders links; the click is human.

Pure stdlib (http.server + sqlite3). Binds 127.0.0.1 by default —
state.db holds data about real people, do not expose it.

One concern per module (mirrors sources/ and db/): state.py holds the DB
handle + shared build state, assets.py the CSS/tabs/favicon, multipart.py
the file-upload parser, layout.py the page chrome, workers.py the
background build/note threads, pages.py the per-route renderers, server.py
the HTTP handler + `main`.

Usage:
    python -m webapp           # serve on http://127.0.0.1:3000

Pages:
    /              daily queue: check off targets, draft notes, rebuild
    /board         what's due (follow-ups, quiet applications, the
                   no-response sweep), then companies by latest stage; each
                   row expands to its timeline; log touchpoints in a dialog
                   (also on queue cards)
    /applications  roles applied to, by status
    /stats         source + fit-score effectiveness
    /gaps          skills the fit keeps flagging as missing
    /profile       import/replace the résumé export
"""
from .server import main

__all__ = ["main"]
