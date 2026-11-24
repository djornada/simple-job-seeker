# simple-job-seeker

> **Work in progress** — under active development, expect rough edges and
> breaking changes.

## Why

A remote job search is mostly triage. Each day goes to checking several job
boards, opening postings to see if they fit, confirming they are still open,
and finding the right people to contact. Little of that time goes to the work
that gets replies.

This tool cuts the triage down to a short, ranked daily queue, so the time
goes to applying and reaching out. A Python pipeline pulls listings from
remote job boards, applies deterministic filters and keyword scoring, and
drops the best matches into one queue with prebuilt LinkedIn search links. A
local web UI tracks outreach and applications.

Nothing touches LinkedIn programmatically. The tool generates links and
ratings; every click is yours. This keeps the account safe from bans. See
`CLAUDE.md` for the rule.

### Where AI is used, and where it is not

The pipeline is deterministic by default. An LLM is called only where
judgment over text is needed, and only if you configure one:

| Step | Uses AI? | Why |
| --- | --- | --- |
| Fetching listings from boards | No | Plain HTTP and feed parsing |
| Language, eligibility and region gates | No | Rules over the posting text |
| Keyword scoring and per-company dedup | No | Deterministic scoring |
| Checking whether a posting has expired | No | HTTP status or the board's API |
| Building LinkedIn and ATS search links | No | URL construction |
| Importing your LinkedIn export | No | Parsing a local ZIP |
| Résumé fit re-rank (optional) | Yes | Judges skills and experience against the posting; needs an imported résumé |
| Connection note drafts (optional) | Yes | Writes a short note in your voice |
| Keyword coverage check (on demand) | Yes | Extracts required terms from a posting |

With no LLM configured or reachable, the queue still builds from the keyword
pipeline alone; the AI features just stay off.

## Demo

Mocked data, no real jobs, companies or people. The daily queue with a
card's résumé fit breakdown, ticking a card off and logging the
touchpoint, then the Board, Applications and the skill gaps on Stats:

![Web UI walkthrough: queue, fit breakdown, logging a touchpoint, Board, Applications, Stats](docs/screenshots/demo.gif)

Still: [the daily queue](docs/screenshots/daily-queue.png).

## Layout

- **`server/`** — Python pipeline: collection, scoring, SQLite state, web
  UI, outreach tracker. Stdlib only. See
  [`server/README.md`](server/README.md).

## Quick start

Run the server with Docker or tmuxinator, below. To run it directly with
Python, see [server/README.md](server/README.md#quick-start).

### With Docker

From the repo root:

```sh
docker compose up -d                                  # web UI at http://127.0.0.1:3000
docker compose run --rm web python3 queue_agent.py    # CLIs, same state
docker compose down
```

Compose mounts `server/` into the container, so `state.db`, `config.toml`,
`server/.env` and `queues/` stay on your machine, shared with the commands above.
After a code change, `docker compose restart` is enough; no rebuild. It
uses host networking (Linux), so the web UI still binds to `127.0.0.1` only
and reaches a local Ollama on `localhost:11434`. The container comes back
with Docker after a reboot until you run `docker compose down`.

It runs as uid/gid 1000. If yours differ (`id -u`, `id -g`), set `UID` and
`GID` in a `.env` at the repo root (gitignored; Compose reads it for variable
substitution, it is not mounted into the container), or files the container
writes won't be yours.

### With tmuxinator

From the repo root:

```sh
tmuxinator start job-seeker  # attach to the job-seeker session
tmuxinator stop job-seeker   # also runs docker compose down
```

Two windows: `web` runs `docker compose up` with the server log (Ctrl-C
stops the container; `Ctrl-b d` detaches from tmux and leaves the session
running), and `shell` opens at the repo root.

## Documentation

| Doc | What's in it |
| --- | --- |
| [`server/README.md`](server/README.md) | Server: quick start, configuration, daily routine, tracker, applications, cron. Full docs in [`server/docs/`](server/docs/README.md) |

## Inspiration and alternatives

- **[ai-job-search](https://github.com/MadsLorentzen/ai-job-search)** by
  Mads Lorentzen: a Claude Code–driven job application system. Several
  planned features here are ported from it (see
  [`server/.specs/ai-job-search-ports/SPEC.md`](server/.specs/ai-job-search-ports/SPEC.md)).
  - Pick it if you want tailored CV and cover letter PDFs, a full
    application tracker from draft to offer, and you already use Claude
    Code.
  - Pick simple-job-seeker if you want a daily outreach queue, a local or
    free model, no dependencies, and nothing that touches LinkedIn
    programmatically.
