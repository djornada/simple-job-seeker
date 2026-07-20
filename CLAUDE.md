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
- db/ — SQLite state layer: `db_connect` (owns the pipeline schema —
  seen_jobs, queued_companies, queue_items, profile — plus lazy ALTERs) and
  `is_new` (dedup + company cooldown). tracker.py keeps its own outreach
  schema on the same state.db; both use CREATE TABLE IF NOT EXISTS.
  queue_agent re-exports `db_connect`/`is_new` so `qa.*` keeps working.
- sources/ — one module per job board (`remoteok`, `remotive`, `wwr`, `hn`),
  each exposing a uniform `fetch(cfg) -> list[Job]`. `sources/base.py` holds
  the shared `Job` model, `_get`, and `strip_html`; `sources/__init__.py` is
  the facade (`REGISTRY` + `collect_jobs`, which drives enabled sources and
  turns a dead board into a warning, not a crash). Add a board by dropping a
  module here and registering it. queue_agent re-exports `Job`/`collect_jobs`
  so `qa.Job` / `qa.collect_jobs` keep working.
- queue_agent.py — the pipeline over `sources.collect_jobs`: scores by
  keyword (role keyword in title required, stack keywords add points),
  filters by location, dedups in SQLite, outputs markdown to `queues/`.
  When a profile is imported, an LLM re-rank stage
  (`rerank_with_resume`) re-scores the keyword-gated shortlist by real fit
  against the resume (one LLM call per job → score + one-line fit note);
  with no profile or the backend down it stays keyword-only. Optional
  `--notes` drafts sub-200-char connection notes via the LLM, seeded with
  the imported profile (headline, skills, and full experience) when present.
  The LLM backend is pluggable via `[llm].provider`: "ollama" (local,
  default) or "openai" (any OpenAI-compatible chat endpoint, e.g. NVIDIA
  NIM). `_llm_generate` dispatches; both backends return None when
  unreachable so the fallback is uniform.
- profile.py — resume ingestion (`import <export.zip>` / `show` CLI, plus a
  reusable `ingest(source)` that takes a path or file-like object). Reads a
  LinkedIn data-export ZIP from local disk (nothing touches LinkedIn),
  builds a full profile text (every position, untruncated), and stores it in
  the `profile` table of state.db. Feeds the re-rank stage and connection notes.
- tracker.py — outreach CLI (add/due/done/board/history); shares the same
  state.db. Company names resolve by prefix when unambiguous.
- webapp.py — local web UI over the same pipeline + state.db (pure stdlib
  http.server, binds 127.0.0.1). Daily queue with per-target check-off, fit
  notes, a résumé indicator, and Ollama note drafting, plus outreach
  board/due/log/history, a `/stats` source-effectiveness page, and a
  `/profile` page to upload the LinkedIn export ZIP (multipart handled by a
  small in-house parser — stdlib dropped `cgi` in 3.13 — then `profile.ingest`;
  file is read locally, nothing is sent to LinkedIn). Builds run in a
  background thread; queue items persist in the queue_items table. Generates
  links only; the click is still human.
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
