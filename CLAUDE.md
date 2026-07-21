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
- `extension/` — Chrome extension (in progress): assists browsing the
  LinkedIn feed, asks `server/` to rate/queue opportunities the user is
  looking at. Read-only against the page — no automated clicks or
  submissions.
