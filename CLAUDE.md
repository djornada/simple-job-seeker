# simple-job-seeker

Personal tooling to support a remote job search.

## Non-negotiable principle
Nothing touches LinkedIn programmatically. No scraping, no automated
visits, no auto-connect. Whatever component is deciding targets — the
Python pipeline or the browser extension — only ever generates links,
ratings, or on-page hints; the click is always human. This protects the
account against bans.

## Layout
- `server/` — Python pipeline: job collection, scoring, SQLite state, and a
  local web UI. See `server/CLAUDE.md` for its architecture.
- `extension/` — Chrome extension (Manifest V3, no build step). On a
  manual click (never automatic/continuous), reads the LinkedIn feed or a
  Jobs page as currently rendered and POSTs it to `server/`'s `/api/rate`
  for scoring; anything that clears the bar lands in the same queue the
  Python pipeline writes to. Read-only against the page — no automated
  clicks or submissions. See `extension/README.md` for setup.
