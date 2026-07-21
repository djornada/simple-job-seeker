# simple-job-seeker

Personal tooling to support a remote job search.

## Non-negotiable principle
Nothing touches LinkedIn programmatically. No scraping, no automated
visits, no auto-connect. The script decides the targets and generates
links; the click is human. This protects the account against bans.

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
  state.db. All use CREATE TABLE IF NOT EXISTS, so creation order doesn't
  matter. queue_agent re-exports the pipeline bits so `qa.*` keeps working.
- sources/ — one module per job board (`remoteok`, `remotive`, `wwr`, `hn`),
  each exposing a uniform `fetch(cfg) -> list[Job]`. `sources/base.py` holds
  the shared `Job` model, `_get`, and `strip_html`; `sources/__init__.py` is
  the facade (`REGISTRY` + `collect_jobs`, which drives enabled sources and
  turns a dead board into a warning, not a crash). Add a board by dropping a
  module here and registering it. queue_agent re-exports `Job`/`collect_jobs`
  so `qa.Job` / `qa.collect_jobs` keep working.
- queue_agent.py — entrypoint + facade + orchestrator. Runs as `python
  queue_agent.py` (kept a module, not a package, so cron/docs invocation is
  unchanged); imports the stage modules below, re-exports them so `qa.*`
  keeps working for the web UI, and holds the two orchestration bits:
  `select_queue` (score → location filter → per-company dedup → cap) and
  `main` (the CLI: collect → select → optional re-rank → render → persist).
- scoring.py — keyword scoring (`score_job`): a role keyword in the title is
  required, stack keywords add points, exclude keywords / non-Brazil-friendly
  locations reject.
- links.py — `build_links`: LinkedIn people-search + Google x-ray URLs for a
  target (URLs only; the click is human).
- render.py — `render` (queue → markdown for `queues/`) and `show_stats`.
- llm/ — pluggable LLM backend, one module per provider (mirrors sources/):
  `ollama.py` (local), `openai.py` (any OpenAI-compatible endpoint, e.g.
  NVIDIA NIM), and `__init__.py` as the facade — `generate` dispatches on
  `[llm].provider` and `strip_think` drops qwen3's `<think>` leakage. Both
  backends return None when unreachable so the fallback is uniform.
- resume.py — resume-in-the-loop over the `llm/` facade: `load_profile_text`
  / `load_profile_bits` read the imported profile; `rerank_with_resume`
  re-scores the keyword-gated shortlist by real fit (one LLM call per job →
  score + one-line fit note); `draft_note` writes sub-200-char connection
  notes seeded with the profile. With no profile or the backend down, the
  pipeline stays keyword-only and notes return None.
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
  state.db via `db.outreach_connect` (re-exported as `tracker.db_connect`
  for the web UI). Company names resolve by prefix when unambiguous.
- webapp/ — local web UI package over the same pipeline + state.db (pure
  stdlib http.server, binds 127.0.0.1; run with `python -m webapp`). One
  concern per module (mirrors sources/ and db/): `state.py` (DB handle +
  shared build/notes state under locks), `assets.py` (CSS/tabs/favicon),
  `multipart.py` (the in-house upload parser — stdlib dropped `cgi` in 3.13),
  `layout.py` (page chrome), `workers.py` (background build/note threads),
  `pages/` (one module per route — queue, board, due, log, company, stats,
  profile — with GET_ROUTES in its facade; add a page by dropping a module
  and registering it, same recipe as sources/), `server.py` (Handler +
  `main`). Daily queue with per-target check-off, fit notes, a résumé
  indicator, and LLM note drafting, plus outreach board/due/log/history, a
  `/stats` source-effectiveness page, and a `/profile` page to upload the
  LinkedIn export ZIP (parsed then `profile.ingest`; file is read locally,
  nothing is sent to LinkedIn). Builds run in a background thread; queue
  items persist in the queue_items table. Generates links only; the click is
  still human.
- config.toml — all configuration (sources, filters, targets, resume, llm
  provider, ollama, openai).
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
