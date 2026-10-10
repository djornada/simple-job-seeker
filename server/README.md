# simple-job-seeker

Daily target queue for your remote job-search outreach. Fetches remote job
boards, filters roles matching your profile, dedups against local state, and
outputs a markdown queue with prebuilt LinkedIn search links.

**Design principle: the script decides, you click.** Nothing here touches
LinkedIn programmatically — no scraping, no automated visits, no auto-connect.
That keeps your account safe. The automation is in the research, not the action.

Start at the [root README](../README.md) for the overview, Docker setup and
the Chrome extension. The full docs live in [`docs/`](docs/README.md).

## Requirements

Python 3.11+ (stdlib only — no pip install needed).
Optional: an LLM for `--notes`, résumé fit and keyword checks — a local
[Ollama](https://ollama.com) by default, or any OpenAI-compatible endpoint
(see `[llm]` in [Configuration](docs/configuration.md#llm)).

To set up Ollama, run `./install.sh` — it checks for Ollama (offering to
install it), detects your GPU's VRAM, pulls a model sized to fit, and
points `config.toml` at it. Pass a name to override: `./install.sh qwen3:8b`.

## Usage

```sh
python3 queue_agent.py             # build today's queue
python3 queue_agent.py --notes     # + draft <200 char connection notes (Ollama)
python3 queue_agent.py -n 5        # smaller queue
python3 queue_agent.py --dry-run   # preview without saving state
python3 queue_agent.py --stats     # pipeline stats
python3 queue_agent.py --recheck   # mark archived postings that were taken down
```

Each run:

1. Fetches RemoteOK (JSON API), Remotive (API), We Work Remotely (RSS),
   HN "Who is hiring?" and freehire.me (one API over ~50 ATS boards)
2. Scores jobs: role keyword in title required; stack keywords add points
3. Drops non-Brazil-friendly locations (`brazil_friendly_only`) and,
   with `[gates]` set, postings you can't be hired for (language,
   citizenship, region-only)
4. Skips jobs already seen and companies queued in the last 30 days (SQLite)
   and, with a résumé imported, has the LLM judge the shortlist's fit (see
   "Résumé fit" under Tuning)
5. Prints the queue and saves it to `queues/YYYY-MM-DD.md`
6. Archives each queued job's full posting text in `state.db`, so it
   survives the post being taken down. The web UI's queue cards link to
   it as "saved posting" (`/posting?uid=…`).

Per target you get: the job post, a LinkedIn people-search link for each role
in `people_roles`, and a Google x-ray search as fallback.

## Daily routine (~5 min)

1. Run the script (or read the file cron generated, see below)
2. For each company: open the recruiter/EM search, visit 2–3 profiles
3. Send 1–2 connection requests with a short note
4. Done. Consistency > volume.

## Tracker

`tracker.py` shares `state.db` with the queue agent. Log every touchpoint,
never lose a follow-up:

```sh
python3 tracker.py add "Acme Corp" --person "Jane Doe" --action connected --followup 5
python3 tracker.py add acme --action replied --note "asked for CV" --followup 2
python3 tracker.py due          # follow-ups due or overdue
python3 tracker.py done 3       # close follow-up #3
python3 tracker.py board        # pipeline by latest stage
python3 tracker.py history acme # full timeline for one company
```

Actions: `visited`, `connected`, `messaged`, `replied`, `meeting`,
`applied`, `rejected`, `offer`, `interview`, `no_response`, `withdrawn`,
`declined`, `hired`. Company names resolve by prefix when unambiguous, so
`acme` finds "acme corp".

### Applications

Track each role you applied to, with a status, and get nudged when one
goes quiet. Nothing is ever sent for you: a follow-up is something you
write yourself, then record.

```sh
python3 tracker.py apply acme "Senior Frontend Engineer" --url https://...
python3 tracker.py move 3 interview --note "call with the EM on Tuesday"
python3 tracker.py followup 3   # you followed up: resets the quiet clock
python3 tracker.py apps         # open applications (--all: finals too)
python3 tracker.py stale        # quiet long enough to follow up
python3 tracker.py sweep        # quiet too long → no_response (asks y/N)
```

- Statuses: open `applied → interview → offer`, forward only; final
  `hired`, `rejected`, `no_response`, `withdrawn`, `declined`. `move
  --force` allows anything else (going backwards, reopening a final one).
- One application per company + role. Every status change and follow-up
  is also logged as an outreach action, so `board`, `history` and the web
  UI's `/board` and `/stats` include it.
- Stale rules live in `config.toml`'s `[applications]`. "Quiet" counts
  days since the last status change or follow-up:
  - `followup_after_days` (10): `stale` and the web UI's Board suggest a
    follow-up…
  - `max_followups` (2): …until you've recorded this many.
  - `no_response_after_days` (60): `sweep` offers to close it as
    `no_response`, and only moves anything after you confirm.

In the web UI: an **I applied** button on each queue card creates the
application from that job (company, title, URL). `/applications` lists
them by status, with forms to move one along or record a follow-up, plus
a form for roles you applied to outside the queue. Board's due section
lists quiet applications and the two-step no-response sweep, and they
count toward the Board tab's badge.

Suggested habit: after the daily queue routine, one `tracker.py add` per
connection sent (with `--followup 5`), and `tracker.py due` every morning.

## Cron

```cron
# weekdays at 8:30
30 8 * * 1-5 cd /path/to/simple-job-seeker/server && python3 queue_agent.py > /dev/null 2>> cron.log
# daily at 7:00: re-check archived postings, mark the ones taken down
0 7 * * * cd /path/to/simple-job-seeker/server && python3 queue_agent.py --recheck >> cron.log 2>&1
```

The queue lands in `queues/` either way, so you can read it whenever.

`--recheck` re-visits archived postings on their own boards (never
LinkedIn: those are skipped without a request, and a board redirect to
LinkedIn isn't followed), one second apart. A 404/410 marks the posting
expired; HN asks Algolia whether the comment still exists, and WWR counts
a redirect to its homepage as gone. Anything else (403, 5xx, timeouts)
just records the check. Expired jobs get an "expired" chip on queue cards,
the saved posting and `/applications`, and sort last on the queue page.

## Tuning

Everything lives in `config.toml`; API keys go in `.env`. The
[root README](../README.md#configuration) has an overview of each section,
[Configuration](docs/configuration.md) every key and default.

### Résumé fit

Once you've imported your LinkedIn export (`/profile` page or
`python3 -m profile import <export.zip>`), the LLM scores each shortlisted
job 0–100 on four dimensions: **skills**, **experience**, **culture** and
**career**, and lists up to 3 strengths, 3 gaps and 5 missing skills. The
overall score is their weighted average, computed by the pipeline rather
than the model, with weights from `[resume.weights]`. How many jobs get
judged and where the cut is: `[resume]` in
[Configuration](docs/configuration.md#resume).

Queue cards show the verdict chip, and **fit breakdown** expands the
per-dimension scores, strengths, gaps and missing skills; the markdown
queue lists the same. Missing skills add up across postings in the Stats
tab's [skill gaps](docs/web-ui.md#skill-gaps), and **Check keywords** on a
card compares one posting against your profile
([Résumé matching](docs/resume-matching.md#4-keyword-coverage-per-posting)).

## Extending

- **New job board:** add a module to `sources/` with a
  `fetch(cfg) -> list[Job]`, register it in `REGISTRY` in
  `sources/__init__.py`, and add its name to `[sources] enabled`. Add it to
  `LIVENESS` too (`http_is_live`, or its own `is_live(url)`), or
  `--recheck` never checks its postings. See
  [Architecture → Sources](docs/architecture.md#sources).
- **Different model:** any OpenAI-compatible endpoint is config only:
  `[llm].provider = "openai"` plus `[openai]`, with the key in `.env` (see
  [Configuration](docs/configuration.md#openai)). For a provider that isn't
  OpenAI-compatible, add a module to `llm/` with the same `generate()` as
  `llm/ollama.py` and select it in `llm/__init__.py`'s `generate()`.
- **Your own tables:** `state.db` is plain SQLite, and `db/` owns the
  schema, one module per concern. Add a module there for anything you want
  to track alongside the pipeline's tables.

## Browser extension

`../extension/` scores whatever's on screen on the LinkedIn feed or a Jobs
page against the same filters and résumé fit, through this server's
`/api/rate`. Setup: [root README](../README.md#browser-extension) and
[`extension/README.md`](../extension/README.md).
