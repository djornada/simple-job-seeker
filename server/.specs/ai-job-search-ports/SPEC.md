# Spec: Ports from ai-job-search

Status: Draft
Date: 2026-10-07

## 1. Problem

[MadsLorentzen/ai-job-search](https://github.com/MadsLorentzen/ai-job-search)
covers ground this repo doesn't. A feature-by-feature map
([artifact](https://claude.ai/artifact/7Dmpuq8VWNuCGhxHkwf49g)) picked seven
features worth porting. Each one maps to a concrete gap in today's code:

- Posting text is capped at 2,000 chars everywhere (`strip_html`'s default
  `limit`, the extension's `.slice(0, 2000)`, `/api/rate`'s `[:2000]`) and
  lives only on `queue_items` rows. When a posting is taken down, the full
  text is gone.
- `score_job` only reads title, tags and location. Nothing catches "fluent
  German required" or "US citizens only". Also, `brazil_friendly_only`
  counts `"remote"` as an ok-marker, so a location like `Remote - US only`
  passes the filter.
- Applications are untyped outreach events per company (`applied`,
  `rejected`, `offer` in `tracker.ACTIONS`). Nothing tracks a role, a
  current status, or how long an application has been quiet.
- Dead postings stay in the queue forever.
- `judge_fit` returns one 0–10 number and one line. There are no
  per-dimension scores, no strengths or gaps, and nothing to aggregate
  across postings.
- There's no way to see which of a posting's keywords the résumé covers.

## 2. Goal

Port seven features, grouped into three milestones:

| Milestone | Ports | Why together |
| --- | --- | --- |
| M1: Capture and gates | 5.1 Posting archive, 5.2 Language and eligibility gates | Foundations. Later ports read the archived text, and the gates cut noise from everything downstream. |
| M2: Application tracking | 5.3 Application stages and stale rules, 5.4 Expired-posting check | The workflow after a job is chosen: what you applied to, what went quiet, what disappeared. |
| M3: Fit insight | 5.5 Weighted fit scoring, 5.6 Skill gaps page, 5.7 Résumé keyword coverage | Richer LLM judgement and the views built on it. |

## 3. Non-negotiables

- **Nothing touches LinkedIn programmatically.** The expired-posting check
  (5.4) refuses any `linkedin.com` host and never re-checks items the
  extension submitted. Follow-ups and sweeps are proposals; nothing is sent
  on the user's behalf.
- Pure stdlib, Python 3.11+. No new dependencies.
- All new data lives in `state.db` (gitignored). Postings and applications
  contain data about real companies and people.
- Graceful degradation: with no profile or the LLM backend down, every port
  either keeps working without the LLM or turns itself off, as today.
- Existing databases migrate in place: `CREATE TABLE IF NOT EXISTS` for new
  tables, guarded `ALTER TABLE ... ADD COLUMN` for new columns (the
  `db_connect` pattern).
- Surgical edits. New code follows the existing recipes: one concern per
  module, registries for routes and sources, adapters (CLI, web UI) calling
  shared `pipeline/` use cases.

## 4. Shared changes

These land with the first port that needs them:

- `Job` (`sources/base.py`) gains `full_text: str = ""` (5.1) and
  `flags: list[str]` (5.2).
- `queue_items` gains `flags TEXT` (5.2), `fit_json TEXT` (5.5) and
  `coverage_json TEXT` (5.7), each JSON-encoded, each added through the
  guarded-ALTER loop in `db_connect`.
- One alias table for keyword matching, shared by 5.6 and 5.7:

  ```toml
  [keywords]
  aliases = { k8s = "kubernetes", js = "javascript", ts = "typescript", postgres = "postgresql" }
  ```

## 5. Components

### 5.1 Posting archive (M1)

Keep the posting text exactly as it was when a job entered the queue.

- `strip_html(raw, limit: int | None = 2000)`: `None` returns the full text.
- Each source sets `full_text=strip_html(raw, None)` and
  `description=full_text[:2000]`, so the LLM prompt size doesn't change.
- New `db/postings.py` owns the table plus `archive_posting(conn, job)`.
  `db_connect()` ensures the schema:

  ```sql
  CREATE TABLE IF NOT EXISTS postings (
      uid         TEXT PRIMARY KEY,   -- same key as queue_items.uid
      source      TEXT NOT NULL,
      url         TEXT NOT NULL,
      company     TEXT NOT NULL,
      title       TEXT NOT NULL,
      location    TEXT NOT NULL DEFAULT '',
      text        TEXT NOT NULL,      -- full_text, else description
      archived_at TEXT NOT NULL,
      checked_at  TEXT,               -- 5.4
      expired_at  TEXT                -- 5.4
  );
  ```

- `INSERT OR IGNORE`, so the first snapshot wins and a later build never
  overwrites it.
- `db.save_queue` calls `archive_posting` for every job it persists. Board
  builds and extension ratings both go through `save_queue`, so both are
  covered. Only queued jobs are archived, not every fetched job.
- Extension: `content/jobs.js` raises the detail-description cap from 2,000
  to 20,000 chars. `/api/rate` keeps `description[:2000]` for the LLM and
  sets `full_text` to the body text capped at 20,000.
- Web UI: new `webapp/pages/posting.py`, `GET /posting?uid=…`, shows the
  archived text, the archive date and the original URL. Queue cards get a
  "saved posting" link when a row exists.

### 5.2 Language and eligibility gates (M1)

Reject postings you can't be hired for before they spend an LLM call.

```toml
[gates]
# Languages you can work in, with your level (CEFR or "native").
languages = { english = "C1", portuguese = "native" }
# Phrases in the posting that mean you can't be hired. Case-insensitive.
eligibility_blockers = [
    "us citizen", "u.s. citizen", "green card", "security clearance",
    "authorized to work in the us", "eu citizen", "eu work permit",
    "right to work in the uk",
]
# Location or title text that restricts hiring to one region, even when "remote".
region_only = [
    "us only", "usa only", "u.s. only", "eu only", "uk only",
    "canada only", "north america only", "remote - us", "remote (us)",
]
```

New `pipeline/gates.py` with `check_gates(job, cfg) -> tuple[str, list[str]]`
(reject kind, flags). The kind is `""` when the job passes, else
`"eligibility"` or `"language"`, which the build summary counts. On a
rejection, flags hold the reason.

- **Eligibility.** A blocker phrase in `full_text or description` rejects
  the job. A `region_only` phrase in location or title also rejects. This
  check runs before the brazil ok-markers, which closes the
  `Remote - US only` hole. Phrases match at a word start, so `us citizen`
  catches `US citizens` but `us only` doesn't catch `focus only`.
  `region_only` applies whether or not `brazil_friendly_only` is on.
- **Language.** Match a fixed list of about 25 human-language names (not
  programming languages, so no "Go" or "Rust" false positives) against
  requirement patterns: `fluent in X`, `X (fluent|native|C1|C2|B2)`,
  `X is required`, `X speaker`, `proficient in X`. A required language
  missing from `[gates].languages` rejects the job. A requested level above
  the declared one (native > C2 > C1 > B2 > B1) adds a flag such as
  `Asks for native English; you declared C1` without rejecting. Also
  `native X`, so "Native English" is read as a native-level request.
  `X or Y` passes when either is declared. A mention softened in the same
  clause ("a plus", "nice to have", "preferred", "not required") never
  rejects; an undeclared one is flagged `X nice-to-have`. An empty
  `languages` table turns the language gate off.
- `score_job` calls `check_gates` first. A rejection returns `0.0`; the
  kind goes on `job.gate`, flags on `job.flags`. `rate_jobs` skips
  `judge_fit` for a gated job and never queues it, so an LLM score can't
  bring it back.
- Flags persist to `queue_items.flags` and show as chips on queue cards,
  in the markdown render and in the extension popup (`/api/rate` returns
  them).
- Each build prints one stderr summary: `[gate] rejected 4 (language 3, eligibility 1)`.
- With no `[gates]` table, gates are off (today's behavior).

### 5.3 Application stages and stale rules (M2)

Track each role you applied to, and surface the ones that went quiet.

New `db/applications.py` owns the table. `outreach_connect()` ensures it,
so the tracker and the web UI both get it:

```sql
CREATE TABLE IF NOT EXISTS applications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company        TEXT NOT NULL,          -- lower-cased, as in outreach
    role           TEXT NOT NULL,
    uid            TEXT,                   -- queue item / posting, when known
    url            TEXT,
    status         TEXT NOT NULL,
    applied_on     TEXT NOT NULL,
    last_activity  TEXT NOT NULL,          -- drives staleness
    followups_sent INTEGER NOT NULL DEFAULT 0,
    note           TEXT,
    UNIQUE (company, role)
);
```

- **Lifecycle.** Open: `applied → interview → offer`. Final: `hired`,
  `rejected`, `no_response`, `withdrawn`, `declined`. Open statuses never
  move backwards. Reopening a final status needs `--force`.
- **One history.** Every transition also appends an outreach event with the
  status as `action`, so `/board`, `/company`, `tracker.py history` and
  `/stats` keep working unchanged. `tracker.ACTIONS` gains `interview`,
  `no_response`, `withdrawn`, `declined` and `hired`, appended after the
  existing entries. `STAGE_ORDER` weights are list positions, and `/stats`
  looks up `connected` and `replied` by name, so appending is safe.
- **Stale rules:**

  ```toml
  [applications]
  followup_after_days = 10     # quiet this long → suggest a follow-up
  max_followups = 2            # stop suggesting after this many
  no_response_after_days = 60  # quiet this long → offer the no-response sweep
  ```

  "Quiet" means today minus `last_activity`, open statuses only. A
  follow-up is suggested when the application is quiet for at least
  `followup_after_days` and `followups_sent < max_followups`. Recording one
  bumps both counters and logs an outreach `messaged` event noted
  "follow-up". The sweep lists open applications quiet for at least
  `no_response_after_days`, and the user confirms before any move to
  `no_response`: a y/N prompt in the CLI, a two-step button in the web UI.
- **CLI** (`tracker.py`): `apply <company> <role> [--url] [--note]`,
  `move <id> <status> [--note] [--force]`, `followup <id>`, `apps [--all]`,
  `stale`, `sweep`.
- **Web UI:** new `webapp/pages/applications.py` at `/applications`, grouped
  by status, with move and follow-up forms that return htmx fragments (the
  `/toggle` pattern). Queue cards get an "I applied" button that creates the
  application from the queue row (company, title, url, uid). `/due` gains a
  "gone quiet" section and the sweep.

### 5.4 Expired-posting check (M2)

Depends on 5.1, which adds `postings.checked_at` and `expired_at`.

- A source module may expose `is_live(url) -> bool | None` (None means
  "can't tell"). `sources/__init__.py` registers them in `LIVENESS`, next to
  `REGISTRY`. The default `http_is_live` in `base.py` sends a GET: 404/410
  means False, 2xx means True, anything else None. `hn` asks the Algolia
  `items/{id}` endpoint, where a deleted or empty comment means False.
- **LinkedIn guard.** `base.py` refuses any URL whose host is `linkedin.com`
  or a subdomain and returns None without a request. Items with source
  `linkedin` (from the extension) are never selected.
- New `pipeline/expiry.py`, `recheck(conn, cfg)`. Candidates are postings
  that aren't expired, were archived at least `min_age_days` ago, and were
  never checked or checked longer ago than `recheck_days`. Least recently
  checked go first, up to `max_checks` per run, with a 1-second pause
  between requests.

  ```toml
  [expiry]
  max_checks = 50
  min_age_days = 2
  recheck_days = 3
  ```

- Run with `python queue_agent.py --recheck`, which suits cron.
- Expired items show an "expired" chip on queue cards and applications, and
  sort last on the queue page.
- Boards that return 200 for a "this job is closed" page are out of scope
  until one is seen in practice. Per-source `is_live` leaves room for it.

### 5.5 Weighted fit scoring (M3)

Replace the single 0–10 judgement with ai-job-search's weighted framework.

New `judge_fit` reply schema:

```json
{
  "skills": 0, "experience": 0, "culture": 0, "career": 0,
  "strengths": ["up to 3 short lines grounded in the posting"],
  "gaps": ["up to 3 short lines"],
  "missing_skills": ["up to 5 short skill names, e.g. \"Kubernetes\""],
  "fit": "one line: why it fits / what to emphasize"
}
```

Each dimension is scored 0–100.

- **Python computes the overall score, never the model.** It's a weighted
  average, with weights from `[resume.weights]` (defaults: skills 30,
  experience 25, culture 15, career 30). Location stays a pass/fail in
  `score_job` and the gates.
- **Verdicts:** strong ≥ 75, good 60–74, moderate 45–59, weak 30–44,
  poor < 30.
- **Compatibility.** `llm_score = overall / 10`, so `min_llm_score`, the
  `/stats` score bands, `render.py` and the extension popup keep working
  unchanged.
- **Career goals.** An optional free-text `[resume].goals` is appended to
  the prompt so the career dimension has something to judge against.
- **Storage.** `queue_items.fit_json` holds the dimensions, strengths, gaps,
  missing_skills, overall and verdict.
- **Defensive parsing.** A missing or non-numeric dimension is dropped and
  the remaining weights renormalized. With no valid dimension, fall back to
  a legacy `score` key if present, else `{}` (unscored), as today.
- **UI.** Queue cards show a verdict chip and a `<details>` with per-dimension
  scores, strengths and gaps. The markdown render prints the verdict and
  bullets.
- Still one LLM call per job. Check JSON compliance on both the Ollama
  (qwen3) and NIM backends.

### 5.6 Skill gaps page (M3)

Depends on 5.5 (`missing_skills`).

- New `webapp/pages/gaps.py` at `/gaps`, with a nav entry.
- Aggregates `fit_json.missing_skills` across `queue_items` within a
  window: `?days=30|90|all`, default 90. Skill names are normalized:
  lower-cased, trimmed, whitespace collapsed, then mapped through
  `[keywords].aliases`.
- Columns: skill; postings (distinct uids); weighted score, the sum of
  `1 − overall/100`, so gaps from weaker fits count more (as in
  ai-job-search's `/upskill`); last seen; up to three example companies
  linked to `/company`.
- Skills already in the profile's `skills_json` are dropped
  (case-insensitive match).
- Sorted by weighted score. The page has an empty state until 5.5 data
  exists.

### 5.7 Résumé keyword coverage (M3)

Depends on 5.1 (full posting text). Independent of 5.5.

- **On demand, not during builds**, so builds stay fast. A "Check keywords"
  button on the queue card starts a background job in `webapp/workers.py`
  (the note-drafting pattern), polled through `GET /coverage-status`.
- New `pipeline/coverage.py`:
  1. `extract_keywords(text, cfg)`: one JSON-mode LLM call returning
     `{"required": [...], "preferred": [...]}` as short terms, from the
     archived posting.
  2. `match(terms, profile_text, aliases)`: deterministic. A word-boundary
     match on the normalized term means `covered`, an alias match means
     `synonym`, otherwise `missing`. There's no LLM in matching, so results
     are reproducible.
- Stored in `queue_items.coverage_json`.
- UI: a table of term, required or preferred, and status, with
  missing-required terms first.

## 6. Files touched

| File | Ports |
| --- | --- |
| `sources/base.py` | 5.1 `full_text`, `strip_html(limit=None)`; 5.2 `flags`; 5.4 `http_is_live`, LinkedIn guard |
| `sources/{remoteok,remotive,wwr,hn}.py` | 5.1 `full_text`; 5.4 `is_live` where needed (`hn`) |
| `sources/__init__.py` | 5.4 `LIVENESS` registry |
| `db/db_connect.py` | 5.1 postings schema; new `queue_items` columns (5.2, 5.5, 5.7) |
| `db/postings.py` (new) | 5.1, 5.4 |
| `db/queue.py` | 5.1 archive on save; 5.2 flags; 5.5 `fit_json` |
| `db/applications.py` (new), `db/outreach.py` | 5.3 |
| `pipeline/gates.py` (new), `pipeline/scoring.py` | 5.2 |
| `pipeline/expiry.py` (new) | 5.4 |
| `pipeline/resume.py` | 5.5 |
| `pipeline/coverage.py` (new) | 5.7 |
| `pipeline/render.py` | 5.2 flags, 5.5 verdict |
| `tracker.py` | 5.3 |
| `queue_agent.py` | 5.4 `--recheck` |
| `webapp/server.py` | 5.1 `/api/rate` full text; 5.2 flags in response; 5.3 POST routes; 5.7 POST route |
| `webapp/pages/{posting,applications,gaps}.py` (new), `queue.py`, `due.py`, `__init__.py` | 5.1, 5.3, 5.5, 5.6, 5.7 |
| `webapp/workers.py` | 5.7 |
| `extension/content/jobs.js`, `extension/popup.js` | 5.1 cap; 5.2 flags |
| `config.toml` | `[gates]`, `[applications]`, `[expiry]`, `[resume.weights]`, `[resume].goals`, `[keywords]` |
| `server/CLAUDE.md`, `server/README.md` | each port documents itself |

## 7. Out of scope

- Follow-up message drafting. It builds on 5.1 and 5.3 and is a good
  candidate for a later spec.
- A learning plan with study resources. There's no web search here, and
  LLM-invented URLs are worse than none.
- CV and cover letter generation, Gmail sync, Notion sync, and
  ai-job-search's `linkedin-search` (it breaks §3).

## 8. Verification

There's no test suite. Verify by hand against a copy of a real `state.db`:

1. **5.1:** build a queue. `postings` has a row for each queued job with
   text longer than 2,000 chars where the board provides it. A second
   build leaves `archived_at` unchanged. `/posting?uid=` renders. Rate a
   Jobs page from the extension and its posting is archived too.
2. **5.2:** a posting with "fluent German required" is rejected. One with
   "native English" passes with a flag. `Remote - US only` is rejected with
   `brazil_friendly_only` on. Removing `[gates]` restores today's results.
3. **5.3:** `tracker.py apply`, then `move` through to `offer`. `history`
   shows every step. Backdate `last_activity` by 11 days and `stale` lists
   the application. Backdate it by 61 days and `sweep` proposes it, and it
   only moves after confirming. The "I applied" button creates a linked row.
4. **5.4:** set a posting's URL to a known 404 and `--recheck` marks it
   expired. A `linkedin.com` URL is skipped without any request (check with
   a debug print or packet capture). `max_checks` is respected.
5. **5.5:** a build fills `fit_json` with all four dimensions. Overall
   matches the weighted average. `llm_score` equals overall / 10. Feed a
   malformed reply and the job is unscored, not crashed. Run once on each
   backend.
6. **5.6:** with 5.5 data, `/gaps` lists skills, excludes ones in the
   profile, and alias variants merge into one row.
7. **5.7:** "Check keywords" fills `coverage_json`. A term worded
   differently but listed in `[keywords].aliases` shows as `synonym`. With
   the LLM down, the button reports the failure and the card stays usable.

## 9. Implementation order

5.1 → 5.2 → 5.3 → 5.4 → 5.5 → 5.6 → 5.7, which is milestone order. Ship
each port as its own commit set, with its docs (`server/CLAUDE.md`
architecture notes, `server/README.md` for usage and config).

## 10. Tracking

Tracking issue: [#8](https://github.com/djornada/simple-job-seeker/issues/8).
Labels: `port:ai-job-search`, `area:*`, `effort:*`.

| Section | Issue | Milestone | Depends on |
| --- | --- | --- | --- |
| 5.1 Posting archive | [#1](https://github.com/djornada/simple-job-seeker/issues/1) | M1: Capture and gates | none |
| 5.2 Language and eligibility gates | [#2](https://github.com/djornada/simple-job-seeker/issues/2) | M1: Capture and gates | none |
| 5.3 Application stages and stale rules | [#3](https://github.com/djornada/simple-job-seeker/issues/3) | M2: Application tracking | none |
| 5.4 Expired-posting check | [#4](https://github.com/djornada/simple-job-seeker/issues/4) | M2: Application tracking | #1 |
| 5.5 Weighted fit scoring | [#5](https://github.com/djornada/simple-job-seeker/issues/5) | M3: Fit insight | none |
| 5.6 Skill gaps page | [#6](https://github.com/djornada/simple-job-seeker/issues/6) | M3: Fit insight | #5 |
| 5.7 Résumé keyword coverage | [#7](https://github.com/djornada/simple-job-seeker/issues/7) | M3: Fit insight | #1 |
