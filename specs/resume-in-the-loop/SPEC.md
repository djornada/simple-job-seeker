# Spec: Resume-in-the-loop job matching

Status: draft
Date: 2026-07-15

## 1. Problem

Job scoring is keyword-only (`score()` in `queue_agent.py`): a role keyword
must appear in the title, stack keywords add points, and every keyword is
hand-maintained in `config.toml`. This is imprecise — it ranks jobs by
surface word overlap, not by actual fit with the owner's experience. The
connection-note prompt in `draft_note()` also hardcodes the owner's profile
as a string, so notes can't reference real, current experience.

## 2. Goal

Put the owner's resume in the scoring loop, sourced from the LinkedIn
**data export ZIP** (Settings → Get a copy of your data), and use it to:

1. re-rank the daily queue by real fit (local LLM judge),
2. generate a per-job fit summary ("why it fits / what to emphasize"),
3. personalize connection notes.

Ride-alongs approved by the owner:

4. Hacker News "Who is hiring?" as a fourth job source,
5. a source-effectiveness stats page in the web UI.

## 3. Non-negotiables

- **Nothing touches LinkedIn programmatically.** The data export is a
  manual, user-initiated download from LinkedIn's own UI. The pipeline only
  reads the ZIP from local disk.
- Pure stdlib, Python 3.11+. No new dependencies.
- All personal data stays local and gitignored (profile goes into
  `state.db`, which already is).
- Graceful degradation: with no profile imported or Ollama down, the
  pipeline behaves exactly as today.

## 4. Components

### 4.1 `profile.py` (new) — resume ingestion CLI

```
python profile.py import ~/Downloads/LinkedInDataExport.zip
python profile.py show
```

- Open the ZIP with `zipfile`; locate `Profile.csv`, `Positions.csv`,
  `Skills.csv` by case-insensitive basename (export layouts vary).
- Parse with `csv.DictReader`, defensively by header name:
  - Profile: `Headline`, `Summary`
  - Positions: `Company Name`, `Title`, `Description`, `Started On`,
    `Finished On`
  - Skills: `Name`
- Build a compact profile text (~1,500 chars): headline, summary, recent
  positions (title @ company + trimmed description), skills list.
- Store in a new `profile` table in `state.db`:

  ```sql
  CREATE TABLE IF NOT EXISTS profile (
      id          INTEGER PRIMARY KEY CHECK (id = 1),
      text        TEXT NOT NULL,
      headline    TEXT,
      skills_json TEXT,
      imported_at TEXT
  );
  ```

- `show` prints the stored profile and import date.
- Reuse `queue_agent.load_config()` and DB conventions via
  `import queue_agent as qa` (same pattern as `webapp.py`).

### 4.2 Job descriptions (modify `queue_agent.py`)

- `Job` dataclass: add `description: str = ""`.
- All three current fetchers already receive descriptions in their
  payloads; capture them:
  - RemoteOK: `item["description"]`
  - Remotive: `description`
  - WWR RSS: `<description>`
- New helper `strip_html()` using an `html.parser.HTMLParser` subclass;
  trim descriptions to ~2,000 chars.
- `queue_items`: add `description` and `fit_note` columns. Guarded
  migration: columns in `CREATE TABLE` for fresh DBs, `ALTER TABLE ...
  ADD COLUMN` in try/except for existing ones.

### 4.3 LLM re-rank stage (modify `queue_agent.py`)

New function `rerank_with_resume(jobs, profile_text, cfg)`:

- Input: keyword-gated jobs sorted by keyword score; take the top
  `[resume].shortlist` (default 30).
- One Ollama `/api/generate` call per job with `format: "json"` and
  `think: false` (qwen3 emits `<think>` otherwise; also strip
  defensively). Prompt: profile text + job title/company/description.
  Expected reply:

  ```json
  {"score": 0-10, "fit": "one line: why it fits / what to emphasize"}
  ```

- Final ranking: LLM score primary, keyword score tiebreak. Drop jobs
  below `[resume].min_llm_score` (default 5; 0 disables the floor).
- Wire in between selection and save. If no profile row exists or Ollama
  is unreachable, skip the stage entirely (today's behavior).
- Persist `fit` to `queue_items.fit_note`; render in the queue markdown
  and on webapp queue cards. Same call as the score — no extra inference.

### 4.4 Resume-aware notes (modify `draft_note()`)

Replace the hardcoded "senior software engineer / tech lead (React,
TypeScript, Node.js)" fragment with headline + top skills from the
`profile` table when present; fall back to the current string when not.

### 4.5 HN "Who is hiring?" source (modify `queue_agent.py`)

`fetch_hn()` via the public Algolia HN API (no auth):

1. `GET https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query="who is hiring"`
   → latest monthly thread id.
2. `GET https://hn.algolia.com/api/v1/items/{id}` → full tree; top-level
   comments are job posts.

Parsing:

- Conventional first line `Company | Role | Location | ...` → Job fields.
- `url = https://news.ycombinator.com/item?id={comment_id}` (link only;
  the click is human, as with every source).
- `description` = stripped comment HTML.
- Skip posts without "remote"; feed location text into the existing
  brazil-friendly filter.
- Enable with `[sources] enabled = [..., "hn"]`.

### 4.6 Source-effectiveness stats (modify `webapp.py`)

New `/stats` page:

- Join queue history (`queued` table) with tracker `outreach` by company
  name (loose text match — fine for personal tooling; state the caveat on
  the page).
- Per source: queued, contacted, replied, reply rate.
- Conversion by LLM-score band once enough data accumulates.

### 4.7 Config (`config.toml`)

```toml
[resume]
shortlist = 30       # jobs sent to LLM re-rank after keyword gate
min_llm_score = 5    # drop jobs the model scores below this (0 disables)
```

### 4.8 Housekeeping

- `.gitignore`: add `*.zip` (in case an export lands in the repo dir).
- `CLAUDE.md`: document `profile.py`, the re-rank stage, the `hn` source
  and `/stats`.

## 5. Files touched

| File | Change |
| --- | --- |
| `profile.py` | new — ingestion CLI |
| `queue_agent.py` | Job.description, strip_html, fetcher capture, fetch_hn, rerank_with_resume, draft_note, schema migration |
| `webapp.py` | fit notes on queue cards, profile indicator, /stats |
| `config.toml` | `[resume]` section, optional `hn` source |
| `CLAUDE.md`, `.gitignore` | docs + ignore rules |

## 6. Verification

1. `python profile.py import <real export zip>`; `profile.py show` prints
   headline/skills/positions.
2. `python queue_agent.py --notes` on the existing `state.db`: migration
   succeeds, queue markdown includes LLM scores and fit lines, notes
   reference the real profile.
3. Stop Ollama and rerun: pipeline degrades to keyword-only, no errors.
4. Enable the `hn` source and rerun: HN jobs parsed with
   company/role/location, brazil filter applied.
5. `python webapp.py`: queue shows fit notes; `/stats` renders real
   counts.

## 7. Implementation order

1. Schema migration + `Job.description` + fetcher capture (`strip_html`).
2. `profile.py` ingest/show.
3. `rerank_with_resume` + fit notes in markdown output.
4. `draft_note` personalization.
5. `fetch_hn`.
6. webapp: fit notes, profile indicator, `/stats`.
7. Config + CLAUDE.md + .gitignore.
