# Configuration

[← Docs home](README.md)

Everything is configured in a single file: **`config.toml`** at the repo root.
It's read fresh on every run, so changes take effect the next time you build a
queue or reload a page. No environment variables, no hidden state.

Below is every section, with the shipped defaults (tuned for a senior
full-stack profile hiring from Brazil).

## `[targets]`

Controls the shape of the daily queue and the outreach links.

```toml
[targets]
per_day = 10                  # how many companies per daily queue
company_cooldown_days = 30    # don't re-queue the same company within N days
people_roles = ["Technical Recruiter", "Engineering Manager"]
```

| Key | Meaning |
| --- | --- |
| `per_day` | Max targets in a queue. Overridable per-run with `-n`. |
| `company_cooldown_days` | A queued company won't reappear for this many days. |
| `people_roles` | Roles to build LinkedIn people-search links for on each card. The first is also used for the Google x-ray. |

## `[sources]`

Which job boards to pull from, and their per-source settings.

```toml
[sources]
enabled = ["remoteok", "remotive", "wwr", "hn"]
remotive_searches = ["react", "frontend", "full stack", "node"]
wwr_feeds = [
    "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
]
```

| Key | Meaning |
| --- | --- |
| `enabled` | The active sources. Available: `remoteok`, `remotive`, `wwr`, `hn` (Hacker News "Who is hiring?"). Remove one to disable it. |
| `remotive_searches` | Search terms queried against the Remotive API. |
| `wwr_feeds` | We Work Remotely RSS category feeds to read. |

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

## `[resume]`

The optional LLM re-rank against your imported résumé. See
[Résumé matching](resume-matching.md).

```toml
[resume]
shortlist = 30       # jobs sent to the LLM re-rank after the keyword gate
min_llm_score = 5    # drop jobs the model scores below this (0 disables)
```

| Key | Meaning |
| --- | --- |
| `shortlist` | How many top keyword-ranked jobs to send through the model. |
| `min_llm_score` | Drop jobs the model scores below this (0–10 scale). `0` keeps everything. |

Has no effect until you import a résumé; ignored if Ollama is unreachable.

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
| `port` | Port for `python -m webapp`. |

## `[ollama]`

The local model used for drafted notes and the résumé re-rank.

```toml
[ollama]
url = "http://localhost:11434"
model = "qwen3.5"
```

| Key | Meaning |
| --- | --- |
| `url` | Where your Ollama server listens. |
| `model` | The model tag to use. `install.sh` sets this to a GPU-fitted `qwen3` automatically. |

---

Next: [Architecture](architecture.md) for how these settings flow through the
pipeline.
