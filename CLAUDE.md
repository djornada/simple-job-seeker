# simple-job-seeker

Personal tooling to support a remote job search.

## Non-negotiable principle
Nothing touches LinkedIn programmatically. No scraping, no automated
visits, no auto-connect. Whatever component is deciding targets — the
Python pipeline — only ever generates links,
ratings, or on-page hints; the click is always human. This protects the
account against bans.

## Layout
- `server/` — Python pipeline: job collection, scoring, SQLite state, and a
  local web UI. See `server/CLAUDE.md` for its architecture.
