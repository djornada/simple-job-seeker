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
  pipeline schema (seen_jobs, queued_companies, queue_items, profile,
  postings) plus lazy ALTERs; `is_new.py` is the dedup + company cooldown
  gate; `queue.py` holds the pipeline writes (`mark_queued`, `save_queue`);
  `postings.py` owns the posting archive (`POSTINGS_SCHEMA`, run by
  `db_connect`, and `archive_posting`, which `save_queue` calls for every
  job it persists — board builds and extension ratings alike; INSERT OR
  IGNORE, so the first snapshot wins, and jobs with no text are skipped so
  a later rating that carries it still lands); `outreach.py`
  (`outreach_connect`) owns the tracker's outreach schema on the same
  state.db, and runs `applications.py`'s `APPLICATIONS_SCHEMA`;
  `applications.py` is the application lifecycle shared by tracker.py and
  webapp/ — `apply` (one row per company + role), `move` (open
  `applied → interview → offer` forward only, finals `hired`/`rejected`/
  `no_response`/`withdrawn`/`declined`, `force` overrides;
  `TransitionError` otherwise), `record_followup`, and the `[applications]`
  stale rules (`stale`, `sweep_candidates`, `sweep`, which only moves ids
  that are still candidates). Every change also appends an outreach event
  with the status as `action`, so board/history/stats need no changes.
  Import it as a module (`from db import applications`); `connect.py`
  (`connect`) is the schema-less Row-factory handle for request-serving
  code (the web server ensures schemas at startup). All
  schemas use CREATE TABLE IF NOT EXISTS, so creation order doesn't matter.
  Both queue_agent.py and webapp/ import straight from here.
- sources/ — one module per job board (`remoteok`, `remotive`, `wwr`, `hn`,
  `freehire` — freehire.me's ATS aggregator; `_location` appends
  "Worldwide"/"Brazil" from its resolved geography for the region filter),
  each exposing a uniform `fetch(cfg) -> list[Job]`. `sources/base.py` holds
  the shared `Job` model, `_get`, and `strip_html` (`limit=None` keeps the
  whole text). Each source sets `Job.full_text` to the untruncated posting
  (archived in `postings`) and `description` to `full_text[:2000]`, the
  slice the LLM sees. `sources/__init__.py` is the facade (`REGISTRY` +
  `collect_jobs`, which drives enabled sources and turns a dead board into
  a warning, not a crash; `LIVENESS`, each board's `is_live(url) -> bool |
  None` for the expiry check — `http_is_live` by default (404/410 gone),
  `hn.is_live` asks Algolia, `wwr.is_live` treats a redirect off
  `/remote-jobs/` as gone). `base.py`'s `is_linkedin` guards every request:
  `_get` refuses LinkedIn hosts, `http_probe` returns None for them without
  a request, and the shared opener won't follow a redirect to LinkedIn.
  Add a board by dropping a module here and registering it.
- queue_agent.py — the CLI entrypoint. Runs as `python queue_agent.py`
  (kept a module, not a package, so cron/docs invocation is unchanged);
  holds `main` only (collect → select → optional re-rank → render →
  persist, plus the `queues/<date>.md` artifact; `--recheck` runs
  `pipeline.recheck` instead and exits) and imports its pieces
  directly from `pipeline`/`db`/`utils` — no facade to keep in sync.
- pipeline/ — the stages between the boards and the daily queue, one concern
  per module: `gates.py` (`check_gates`: the `[gates]` language and
  eligibility gates — an eligibility blocker in the posting text or a
  region-only phrase in location/title rejects, a required human language
  you haven't declared rejects, a higher requested level only flags; off
  without a `[gates]` table); `scoring.py` (`score_job`: gates first —
  `job.gate` holds the reject kind, `job.flags` the notes — then role
  keyword in title required, stack keywords add points,
  exclude/non-Brazil-friendly reject); `select.py` (`select_queue`: score
  → filter → per-company dedup → cap, plus one `[gate] rejected N` stderr
  line per build when `[gates]` is set);
  `resume.py` (resume-in-the-loop over the `llm/` facade —
  `rerank_with_resume` re-scores the keyword-gated shortlist by real fit,
  `judge_fit` is the single-job primitive it batches over (also used by
  rate.py): the model scores skills/experience/culture/career 0-100 plus
  strengths, gaps and missing_skills (`[resume].goals` feeds career);
  `fit.py` parses that defensively (`parse_json_object` tolerates fences
  and prose; a bad dimension is dropped and weights renormalized; a legacy
  0-10 `score` is still read) and weighs it with `[resume.weights]` into
  overall + verdict, never trusting the model's arithmetic. `llm_score` =
  overall / 10, so `min_llm_score`, /stats bands, render.py and the popup
  keep their 0-10 scale; the breakdown rides on `Job.fit_detail` into
  `queue_items.fit_json` and renders as a verdict chip + `<details>` on
  queue cards (`pages/queue.py`'s `_fit_block`) and as markdown lines;
  `keywords.py` (`clean`, then `alias_map`/`normalize`: lower-case, trim,
  collapse whitespace, then `[keywords.aliases]`; shared by `/gaps` and
  keyword coverage); `coverage.py` (`check_coverage`, on demand only:
  `extract_keywords` is one JSON-mode, temperature-0 LLM call over the
  archived posting (first 8,000 chars) for required/preferred terms,
  dropping any the posting doesn't contain under some alias spelling — a
  substring check, since board text can run words together; `match` is
  deterministic: whole-word in the profile text is `covered`, another
  alias spelling `synonym`, else `missing`; rows sorted missing-required
  first; None = LLM unreachable, {} = no usable terms); `draft_note`
  writes `NOTE_LIMIT` (200)-char connection notes in the candidate's voice
  to an unnamed `people_roles` reader — role + company first, then one
  result; given `job.description` (build time) or the archived
  `postings.text[:2000]` (`note_worker`), it replies JSON-mode with the
  posting's need and the matching experience before the note, at
  temperature 0.3, so the result fits the posting instead of always being
  the headline one (title-only, plain text, 0.7 without a posting);
  `_tidy_note` strips named greetings/sign-offs, an over-long
  draft gets one retry with its length fed back, then `_fit_note` cuts at
  the last full sentence — profile readers included; with no
  profile or the backend down the pipeline stays keyword-only and notes
  return None); `build.py` (`build_queue`: the
  shared use case — collect → select → optional re-rank — consumed
  directly by both queue_agent.py's `main` and webapp's `build_worker`, so
  the two adapters can't drift apart; with a profile it selects and judges
  a pool of max(1.5 × limit, `[resume].shortlist`) so the
  `min_llm_score` cut still fills the queue, and passes `on_progress`
  through to `rerank_with_resume`, which `build_worker` turns into
  `BUILD["progress"]` for the banner); `rate.py` (`rate_jobs`: the third
  use case — scores ad-hoc jobs/posts the browser extension POSTs to
  `/api/rate` via `score_job` + `judge_fit` and persists anything that
  clears the bar via `db.save_queue`, same as `build_queue` does for
  board-sourced jobs; a gated job skips `judge_fit` and is never queued);
  `expiry.py` (`recheck`: archived postings that aren't expired, are at
  least `min_age_days` old and weren't checked within `recheck_days`, least
  recently checked first, up to `max_checks`, 1 s apart, through the
  source's `LIVENESS` check; False sets `postings.expired_at`, anything
  else only `checked_at`; sources missing from LIVENESS, like the
  extension's LinkedIn items, are never selected); `links.py`
  (`build_links`: LinkedIn people-search + Google x-ray URLs — URLs only,
  the click is human); `render.py`
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
- tracker.py — outreach CLI (add/due/done/board/history) plus
  applications (apply/move/followup/apps/stale/sweep, over
  `db.applications`; `sweep` asks y/N); shares the same state.db via
  `db.outreach_connect`. Company names resolve by prefix when unambiguous.
  `ACTIONS` is append-only: `STAGE_ORDER` weights are list positions, and
  `/stats` looks `connected`/`replied` up by name.
- webapp/ — local web UI package over the same pipeline + state.db (pure
  stdlib http.server, binds 127.0.0.1; run with `python -m webapp`). One
  concern per module (mirrors sources/ and db/): `state.py` (DB handle +
  shared build/notes/coverage state under locks), `assets.py` (CSS/tabs/
  favicon/vendored htmx bytes), `multipart.py` (the in-house upload parser — stdlib
  dropped `cgi` in 3.13), `layout.py` (page chrome), `workers.py`
  (background build/note/coverage threads — `build_worker` calls
  `pipeline.build_queue`, the same use case the CLI uses), `pages/` (one
  module per route — queue, board, applications, posting, stats, gaps,
  profile; plus due, the section Board renders on top, and logform: the
  log-touchpoint `<dialog>` Board and queue cards share, filled by htmx
  from `/log-form` or rendered open by `/board?log=` without JS; ticking a
  card fills it out of band (`queue.log_prompt`, offer only, saved via
  htmx back into the card) — with
  GET_ROUTES in its facade; add a page by dropping a module and
  registering it, same recipe as sources/),
  `server.py` (Handler + `main`). Every module
  imports what it needs straight from `pipeline`/`db`/`sources`/`utils`
  rather than through queue_agent.py — the two adapters (CLI and web UI) sit
  side by side on the same core instead of one depending on the other. Daily
  queue with per-target check-off, fit notes, a résumé indicator, and LLM
  note drafting, plus an outreach board with what's due on top (rows
  expand to each company's timeline; `POST /add` lands on
  `/board?open=<company>`, and the old `/company`/`/log`/`/due` URLs
  redirect there), a `/stats` source-effectiveness page, and a `/profile` page to upload the LinkedIn
  export ZIP (parsed then `profile.ingest`; file is read locally, nothing is
  sent to LinkedIn). Builds run in a background thread; queue items persist
  in the queue_items table. Generates links only; the click is still human.
  `POST /api/rate` (in `server.py`, alongside the other POST handlers) is
  the one route meant for cross-origin callers — the `../extension/` —
  gated by the `X-Extension-Token` header against `[extension].token` in
  config.toml rather than the same-origin check (`origin_ok`) the web UI's
  own forms rely on; it trims each item's description to 2,000 chars for
  the LLM and keeps up to 20,000 as `full_text` for the archive, and
  returns each item's gate `flags` for the popup. Flags persist as JSON in
  `queue_items.flags` and render as amber chips on queue cards (and as a
  `- Flags:` line in the markdown queue).
  `GET /posting?uid=` shows a job's archived text, archive date and
  original URL; queue cards link to it ("saved posting") when a row exists
  (`pages/queue.py`'s `ITEM_SELECT` adds the `archived` flag). Applications:
  an "I applied" button on each queue card (`POST /apply` with date + uid;
  `ITEM_SELECT`'s `app_id` turns it into an "applied ✓" link),
  `/applications` grouped by status with move/follow-up forms answering
  htmx with the re-rendered row (`render_app`, the `/toggle` pattern) and a
  form for roles applied to outside the queue (`POST /apply` with company
  + role), and in Board's due section a "gone quiet" list plus a two-step
  no-response sweep (`/board?sweep=confirm`, then `POST
  /applications/sweep`). Quiet applications add to the Board tab's badge
  (`layout.page`). Expired
  postings (`postings.expired_at`, via `ITEM_SELECT` and
  `pages/applications.py`'s `expired_on`) get an "expired" chip on queue
  cards, `/posting` and `/applications`, and sort last on the queue.
  `/gaps` aggregates `fit_json.missing_skills` over `?days=30|90|all`
  (latest row per uid, so a re-queued job counts once): postings, weighted
  score (sum of 1 − overall/100), last seen, three example companies;
  skills in the profile's `skills_json` are dropped after the same
  normalization. Keyword coverage: "Check keywords" on a queue card
  (`POST /coverage`, the `/note` pattern: `coverage_worker` thread,
  `COVERAGE_PENDING`/`COVERAGE_FAILED` in state.py, the latter uid →
  reason) stores `check_coverage`'s result in `queue_items.coverage_json`;
  `pages/queue.py`'s `coverage_block` renders the table in a `<details>`
  (opened by the `GET /coverage-status` poll that delivers it), and the
  button only shows with a saved posting and a profile (`ITEM_SELECT`'s
  `archived` and `profiled`). The `/`
  queue page uses htmx (vendored at
  `webapp/static/htmx.min.js`, served from `server.py`, never a CDN — the
  webapp still makes no outbound browser requests) for in-place updates:
  toggling an item, drafting a note, checking keywords, and running a
  build all respond with an HTML fragment when the request carries
  `HX-Request: true` (see `pages/queue.py`'s `render_item`/`note_block`/
  `coverage_block`/`_build_section`), falling back to a normal redirect
  otherwise so the plain `<form>` still works with JS off. Note-drafting,
  keyword checks and build-progress poll their own scoped element
  (`GET /note-status`, `GET /coverage-status`, `GET /build-status`)
  instead of the old blanket `<meta refresh>`. See `.specs/htmx-queue-page/SPEC.md` for the design.
- config.toml — all configuration (sources, filters, gates, targets,
  resume + resume.weights, keywords.aliases, expiry, applications, llm
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
