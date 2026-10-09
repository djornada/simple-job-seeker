# Configuration

[← Docs home](README.md)

Everything is configured in a single file: **`server/config.toml`**. It's
read fresh on every run, so changes take effect the next time you build a
queue or reload a page.

The one exception is secrets. API keys never go in `config.toml` (it's
committed); they live in **`server/.env`** (gitignored), one `KEY=value`
per line. Real environment variables win over `.env`. See
[`[openai]`](#openai).

Below is every section, with the shipped defaults (tuned for a senior
full-stack profile hiring from Brazil). Most people only touch
[`[filters]`](#filters), [`[gates]`](#gates) and [`[sources]`](#sources).

## `[targets]`

Controls the shape of the daily queue and the outreach links.

```toml
[targets]
per_day = 30                  # how many companies per daily queue
company_cooldown_days = 30    # don't re-queue the same company within N days
people_roles = ["Technical Recruiter", "Engineering Manager"]
```

| Key | Meaning |
| --- | --- |
| `per_day` | Max targets in a queue. Overridable per-run with `-n`. Worked cards collapse to one line on the web UI. |
| `company_cooldown_days` | A queued company won't reappear for this many days. |
| `people_roles` | Roles to build LinkedIn people-search links for on each card. The first is also used for the Google x-ray. |

## `[sources]`

Which job boards to pull from, and their per-source settings.

```toml
[sources]
enabled = ["remoteok", "remotive", "wwr", "hn", "freehire"]
remotive_searches = ["react", "frontend", "full stack", "node"]
wwr_feeds = [
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
]
freehire_searches = ["react", "frontend", "full stack", "node"]
freehire_regions = ["latam", "global"]
freehire_countries = ["br"]
freehire_days = 14
freehire_skip = ["remotive", "whatjobs"]
```

| Key | Meaning |
| --- | --- |
| `enabled` | The active sources. Available: `remoteok`, `remotive`, `wwr`, `hn` (Hacker News "Who is hiring?"), `freehire` (freehire.me, one API over ~50 ATS boards: Greenhouse, Lever, Ashby, Gupy, GetOnBrd…). Remove one to disable it. |
| `remotive_searches` | Search terms queried against the Remotive API. |
| `wwr_feeds` | We Work Remotely RSS category feeds to read. |
| `freehire_searches` | Search terms queried against freehire.me (remote roles only, 50 per term). |
| `freehire_regions` / `freehire_countries` | freehire's resolved geography (`latam`, `global`, `eu`, …; ISO alpha-2 codes), OR'd into one filter. A job tagged `global` or `br` gets "Worldwide"/"Brazil" appended to its location so `brazil_friendly_only` sees it; a bare LATAM country doesn't. |
| `freehire_days` | Only postings from the last N days. |
| `freehire_skip` | freehire sub-sources to drop, by prefix: `remotive` duplicates that source, `whatjobs` links are paid-click redirects. |

Adding a whole new board is a code change, not a config one — see
[Architecture → Sources](architecture.md#sources).

## `[filters]`

The keyword gate — how roles are scored and rejected. See
[Concepts → How scoring works](concepts.md#how-scoring-works).

```toml
[filters]
role_keywords = [
    "senior", "staff", "lead", "principal",
    "frontend", "front-end", "front end",
    "fullstack", "full-stack", "full stack",
]
stack_keywords = [
    "react", "next.js", "nextjs", "typescript",
    "node", "nestjs", "azure", "gcp", "javascript",
]
exclude_keywords = [
    "junior", "intern", "unpaid", "wordpress", "php",
    "director", "vp ", "recruiter",
]
brazil_friendly_only = true
```

| Key | Meaning |
| --- | --- |
| `role_keywords` | At least one must appear in the job **title** or the job is rejected. Each match adds to the score. |
| `stack_keywords` | Each one found in the title/tags adds a smaller amount to the score. |
| `exclude_keywords` | If any appears in the title, the job is rejected. |
| `brazil_friendly_only` | When `true`, keep only jobs whose location allows hiring from Brazil (worldwide / anywhere / LATAM / americas / brazil / global / remote). Set `false` to drop the region filter. |

## `[gates]`

Reject postings you can't be hired for, before they spend an LLM call.
Delete the whole table to turn the gates off. Each build prints
`[gate] rejected N (language X, eligibility Y)` to stderr.

```toml
[gates]
languages = { english = "C1", portuguese = "native" }
eligibility_blockers = [
    "us citizen", "u.s. citizen", "green card", "security clearance",
    "authorized to work in the us", "eu citizen", "eu work permit",
    "right to work in the uk",
]
region_only = [
    "us only", "usa only", "u.s. only", "eu only", "uk only",
    "canada only", "north america only", "remote - us", "remote (us)",
]
```

| Key | Meaning |
| --- | --- |
| `languages` | Languages you work in, with your level (CEFR `A1`–`C2` or `"native"`). A posting that requires one you haven't listed ("fluent in German", "German (C1)", "German is required") is rejected; "German or English" passes if either is listed. Asking for a higher level than yours ("native English" vs your `C1`) only adds a flag. A mention softened nearby ("a plus", "nice to have", "preferred") never rejects. Only human languages count, so "Go" or "Rust" never trigger it. Empty = no language gate. |
| `eligibility_blockers` | Phrases in the posting text that reject it. |
| `region_only` | Phrases in the location or title that reject it, even when the location also says remote. Applies whether or not `brazil_friendly_only` is on. |

Phrases are case-insensitive and match at a word start, so `us citizen`
also catches "US citizens". Flags show as chips on the web UI's queue
cards, as a `Flags:` line in `queues/<date>.md`, and in the extension
popup, which also shows why a skipped item was rejected.

## `[resume]`

The optional LLM re-rank against your imported résumé. See
[Résumé matching](resume-matching.md).

```toml
[resume]
shortlist = 30       # min jobs sent to the LLM re-rank after the keyword gate
min_llm_score = 5    # drop jobs the model scores below this (0 disables)
# goals = "Staff-level frontend or full-stack role, product company, async remote"
```

| Key | Meaning |
| --- | --- |
| `shortlist` | The minimum number of top keyword-ranked jobs to send through the model. A build judges 1.5 × `[targets] per_day` when that's more (45 for a queue of 30), so the `min_llm_score` cut still leaves a full queue. One LLM call each. |
| `min_llm_score` | Drop jobs scoring below this, on a 0–10 scale (overall / 10). `0` keeps everything. |
| `goals` | Optional free text about what you want next. The **career** dimension judges against it; without it, the model reads your profile's trajectory. |

Has no effect until you import a résumé; ignored if the LLM is
unreachable.

### `[resume.weights]`

The model scores each job 0–100 on four dimensions. The overall score is
their weighted average, computed by the pipeline rather than the model.

```toml
[resume.weights]
skills = 30
experience = 25
culture = 15
career = 30
```

Verdicts on the overall score: strong ≥ 75, good ≥ 60, moderate ≥ 45,
weak ≥ 30, poor below. A reply missing a dimension is scored on the rest,
reweighted; one that can't be parsed leaves the job unscored.

## `[keywords.aliases]`

Spellings of the same skill, as `variant = "canonical"`. Matching is
case-insensitive.

```toml
[keywords.aliases]
k8s = "kubernetes"
js = "javascript"
ts = "typescript"
postgres = "postgresql"
"next.js" = "nextjs"
"node.js" = "node"
nodejs = "node"
"react.js" = "react"
reactjs = "react"
```

Used in two places:

- **Skill gaps** (on [Stats](web-ui.md#skill-gaps)) merges the variants into one row, including when
  dropping skills your profile already has.
- **Keyword coverage** ([Résumé matching](resume-matching.md#4-keyword-coverage-per-posting))
  marks a posting term as `synonym` when your profile has it under another
  spelling in the same group. All spellings that map to one canonical form
  count, so `nodejs` in a posting matches `Node.js` in your profile.

Add a line whenever a coverage check shows `missing` for something you have
under a different name.

## `[expiry]`

Limits for `queue_agent.py --recheck`, which re-visits archived postings on
their own boards (never LinkedIn), one second apart, and marks the ones
taken down as expired.

```toml
[expiry]
max_checks = 50    # requests per run
min_age_days = 2   # leave freshly queued postings alone
recheck_days = 3   # don't re-check a posting more often than this
```

| Key | Meaning |
| --- | --- |
| `max_checks` | Max requests per `--recheck` run. |
| `min_age_days` | Skip postings archived less than this many days ago. |
| `recheck_days` | Don't re-check the same posting within this many days. |

## `[applications]`

Stale rules for tracked applications (`tracker.py apply/move/stale/sweep`,
`/applications`, the Board's due section). "Quiet" counts days since the
application's last status change or follow-up, open statuses only.

```toml
[applications]
followup_after_days = 10     # quiet this long → suggest a follow-up
max_followups = 2            # stop suggesting after this many
no_response_after_days = 60  # quiet this long → offer the no-response sweep
```

| Key | Meaning |
| --- | --- |
| `followup_after_days` | `tracker.py stale` and the Board suggest a follow-up… |
| `max_followups` | …until you've recorded this many. |
| `no_response_after_days` | `tracker.py sweep` offers to close it as `no_response`, and only moves anything after you confirm. |

## `[web]`

The local web server.

```toml
[web]
host = "127.0.0.1"   # keep it local: state.db holds data about real people
port = 3000
```

| Key | Meaning |
| --- | --- |
| `host` | Bind address. **Leave as `127.0.0.1`** — the app is not meant to be network-exposed. |
| `port` | Port for `python -m webapp`. If you change it, change the extension's **Server URL** too. |

## `[llm]`

Which backend drives the résumé re-rank, connection notes and keyword
coverage.

```toml
[llm]
provider = "ollama"
```

| Key | Meaning |
| --- | --- |
| `provider` | `"ollama"` (default): a local model, private, no API key — see [`[ollama]`](#ollama). `"openai"` (also `"nvidia"`, `"nim"`): any OpenAI-compatible chat endpoint — see [`[openai]`](#openai). |

## `[ollama]`

The local model, used when `[llm].provider = "ollama"`.

```toml
[ollama]
url = "http://localhost:11434"
model = "qwen3:14b"
```

| Key | Meaning |
| --- | --- |
| `url` | Where your Ollama server listens. |
| `model` | The model tag to use. `install.sh` sets this to a GPU-fitted `qwen3` automatically. |

## `[openai]`

An OpenAI-compatible endpoint, used when `[llm].provider = "openai"`.
Ships pointed at NVIDIA NIM.

```toml
[openai]
base_url = "https://integrate.api.nvidia.com/v1"
api_key_env = "NVIDIA_API_KEY"
model = "z-ai/glm-5.2"
```

| Key | Meaning |
| --- | --- |
| `base_url` | The endpoint's base URL. |
| `api_key_env` | The **name** of the environment variable holding the key (defaults to `OPENAI_API_KEY`). The key itself goes in `server/.env` — `NVIDIA_API_KEY="nvapi-..."` — or your shell, never in `config.toml`. |
| `model` | The model name the endpoint expects. |

## `[extension]`

The Chrome extension (`extension/`) POSTs items it reads off LinkedIn to
`/api/rate` for scoring.

```toml
[extension]
token = ""
```

| Key | Meaning |
| --- | --- |
| `token` | Shared secret the extension sends as `X-Extension-Token`. Blank = the endpoint is disabled. Set any random string here and paste the same value into the extension popup's **Token** field. |

---

Next: [Architecture](architecture.md) for how these settings flow through the
pipeline.
