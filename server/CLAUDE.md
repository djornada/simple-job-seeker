# server

Python pipeline: collects job listings, scores/dedupes them, and serves a
local web UI over the shared SQLite state. See the repo-root `CLAUDE.md`
for the non-negotiable principle that applies to this and every other
component (e.g. `extension/`).

## Architecture
- utils/ — shared paths (`BASE_DIR`, `CONFIG_PATH`, `ENV_PATH`, `DB_PATH`,
  `OUT_DIR`) and config loading (`load_config`, which also loads a local
  `.env` via `_load_dotenv`). Single source of truth for on-disk locations,
  imported by both the CLI and the web UI without pulling in the pipeline.
- db/ — SQLite state layer, one concern per module: `db_connect.py` owns the
  pipeline schema (seen_jobs, queued_companies, queue_items, profile) plus
  lazy ALTERs; `is_new.py` is the dedup + company cooldown gate; `queue.py`
  holds the pipeline writes (`mark_queued`, `save_queue`); `outreach.py`
  (`outreach_connect`) owns the tracker's outreach schema on the same
  state.db; `connect.py` (`connect`) is the schema-less Row-factory handle
  for request-serving code (the web server ensures schemas at startup). All
  schemas use CREATE TABLE IF NOT EXISTS, so creation order doesn't matter.
  Both queue_agent.py and webapp/ import straight from here.
- sources/ — one module per job board (`remoteok`, `remotive`, `wwr`, `hn`),
  each exposing a uniform `fetch(cfg) -> list[Job]`. `sources/base.py` holds
  the shared `Job` model, `_get`, and `strip_html`; `sources/__init__.py` is
  the facade (`REGISTRY` + `collect_jobs`, which drives enabled sources and
  turns a dead board into a warning, not a crash). Add a board by dropping a
  module here and registering it.
- queue_agent.py — the CLI entrypoint. Runs as `python queue_agent.py`
  (kept a module, not a package, so cron/docs invocation is unchanged);
  holds `main` only (collect → select → optional re-rank → render →
  persist, plus the `queues/<date>.md` artifact) and imports its pieces
  directly from `pipeline`/`db`/`utils` — no facade to keep in sync.
- pipeline/ — the stages between the boards and the daily queue, one concern
  per module: `scoring.py` (`score_job`: role keyword in title required,
  stack keywords add points, exclude/non-Brazil-friendly reject);
  `select.py` (`select_queue`: score → filter → per-company dedup → cap);
  `resume.py` (resume-in-the-loop over the `llm/` facade —
  `rerank_with_resume` re-scores the keyword-gated shortlist by real fit,
  `judge_fit` is the single-job primitive it batches over (also used by
  rate.py), `draft_note` writes sub-200-char connection notes, profile
  readers included; with no profile or the backend down the pipeline stays
  keyword-only and notes return None); `build.py` (`build_queue`: the
  shared use case — collect → select → optional re-rank — consumed
  directly by both queue_agent.py's `main` and webapp's `build_worker`, so
  the two adapters can't drift apart); `rate.py` (`rate_jobs`: the third
  use case — scores ad-hoc jobs/posts the browser extension POSTs to
  `/api/rate` via `score_job` + `judge_fit` and persists anything that
  clears the bar via `db.save_queue`, same as `build_queue` does for
  board-sourced jobs); `links.py` (`build_links`: LinkedIn people-search +
  Google x-ray URLs — URLs only, the click is human); `render.py`
  (`render` queue → markdown + `show_stats`, CLI-only).
- llm/ — pluggable LLM backend, one module per provider (mirrors sources/):
  `ollama.py` (local), `openai.py` (any OpenAI-compatible endpoint, e.g.
  NVIDIA NIM), and `__init__.py` as the facade — `generate` dispatches on
  `[llm].provider` and `strip_think` drops qwen3's `<think>` leakage. Both
  backends return None when unreachable so the fallback is uniform.
- profile/ — resume ingestion package, one concern per module (mirrors
  sources/ and db/): `parse.py` builds the profile from the export ZIP,
  `ingest.py` persists it, `cli.py` is the `python -m profile import
  <export.zip>` / `show` CLI (via `__main__.py`). The facade re-exports
  `ingest`/`ProfileError`/`build_profile`; `ingest(source)` takes a path or
  file-like object. Reads a LinkedIn data-export ZIP from local disk (nothing
  touches LinkedIn), builds a full profile text (every position, untruncated),
  and stores it in the `profile` table of state.db. Feeds the re-rank stage
  and connection notes.
- tracker.py — outreach CLI (add/due/done/board/history); shares the same
  state.db via `db.outreach_connect`. Company names resolve by prefix when
  unambiguous.
- webapp/ — local web UI package over the same pipeline + state.db (pure
  stdlib http.server, binds 127.0.0.1; run with `python -m webapp`). One
  concern per module (mirrors sources/ and db/): `state.py` (DB handle +
  shared build/notes state under locks), `assets.py` (CSS/tabs/favicon/
  vendored htmx bytes), `multipart.py` (the in-house upload parser — stdlib
  dropped `cgi` in 3.13), `layout.py` (page chrome), `workers.py`
  (background build/note threads — `build_worker` calls
  `pipeline.build_queue`, the same use case the CLI uses), `pages/` (one
  module per route — queue, board, due, log, company, stats, profile — with
  GET_ROUTES in its facade; add a page by dropping a module and registering
  it, same recipe as sources/), `server.py` (Handler + `main`). Every module
  imports what it needs straight from `pipeline`/`db`/`sources`/`utils`
  rather than through queue_agent.py — the two adapters (CLI and web UI) sit
  side by side on the same core instead of one depending on the other. Daily
  queue with per-target check-off, fit notes, a résumé indicator, and LLM
  note drafting, plus outreach board/due/log/history, a `/stats`
  source-effectiveness page, and a `/profile` page to upload the LinkedIn
  export ZIP (parsed then `profile.ingest`; file is read locally, nothing is
  sent to LinkedIn). Builds run in a background thread; queue items persist
  in the queue_items table. Generates links only; the click is still human.
  `POST /api/rate` (in `server.py`, alongside the other POST handlers) is
  the one route meant for cross-origin callers — the `../extension/` —
  gated by the `X-Extension-Token` header against `[extension].token` in
  config.toml rather than the same-origin check (`origin_ok`) the web UI's
  own forms rely on. The `/` queue page uses htmx (vendored at
  `webapp/static/htmx.min.js`, served from `server.py`, never a CDN — the
  webapp still makes no outbound browser requests) for in-place updates:
  toggling an item, drafting a note, and running a build all respond with an
  HTML fragment when the request carries `HX-Request: true` (see
  `pages/queue.py`'s `render_item`/`note_block`/`_build_section`), falling
  back to a normal redirect otherwise so the plain `<form>` still works with
  JS off. Note-drafting and build-progress poll their own scoped element
  (`GET /note-status`, `GET /build-status`) instead of the old blanket
  `<meta refresh>`. See `.specs/htmx-queue-page/SPEC.md` for the design.
- config.toml — all configuration (sources, filters, targets, resume, llm
  provider, ollama, openai, extension token).
- install.sh — bash setup helper: ensures Ollama is installed, detects GPU
  VRAM (nvidia-smi, or amdgpu sysfs for AMD), picks a fitting qwen3 model
  from a size ladder, pulls it, and updates the `[ollama]` model in
  config.toml.
- state.db, queues/ and cron.log are local and gitignored (they contain
  data about real people).

## Conventions
- Pure stdlib, no dependencies.
- Python 3.11+ (uses tomllib).
- Surgical edits, no rewrites.

## Owner context
Senior SWE / Tech Lead, stack React/Next/TS/Node/NestJS, based in Brazil,
looking for international remote roles (hence the `brazil_friendly_only`
location filter). Local Ollama on an AMD Radeon RX 6700 XT 12GB — models
up to ~14B in Q4 fit entirely on the GPU.
