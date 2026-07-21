# simple-job-seeker

Daily target queue for your remote job-search outreach. Fetches remote job
boards, filters roles matching your profile, dedups against local state, and
outputs a markdown queue with prebuilt LinkedIn search links.

**Design principle: the script decides, you click.** Nothing here touches
LinkedIn programmatically — no scraping, no automated visits, no auto-connect.
That keeps your account safe. The automation is in the research, not the action.

## Requirements

Python 3.11+ (stdlib only — no pip install needed).
Optional: [Ollama](https://ollama.com) running locally for `--notes`.

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
```

Each run:

1. Fetches RemoteOK (JSON API), Remotive (API), We Work Remotely (RSS)
2. Scores jobs: role keyword in title required; stack keywords add points
3. Drops non-Brazil-friendly locations (`brazil_friendly_only`)
4. Skips jobs already seen and companies queued in the last 30 days (SQLite)
5. Prints the queue and saves it to `queues/YYYY-MM-DD.md`

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
`applied`, `rejected`, `offer`. Company names resolve by prefix when
unambiguous, so `acme` finds "acme corp".

Suggested habit: after the daily queue routine, one `tracker.py add` per
connection sent (with `--followup 5`), and `tracker.py due` every morning.

## Cron

```cron
# weekdays at 8:30
30 8 * * 1-5 cd /path/to/simple-job-seeker/server && python3 queue_agent.py > /dev/null 2>> cron.log
```

The queue lands in `queues/` either way, so you can read it whenever.

## Tuning

Everything lives in `config.toml`:

- `per_day` — queue size (10 is plenty; you won't act on more)
- `company_cooldown_days` — avoid pestering the same company
- `role_keywords` / `stack_keywords` / `exclude_keywords` — scoring
- `people_roles` — who to look for (recruiters, EMs, heads of eng…)
- `brazil_friendly_only` — set `false` to see everything

## Extending

- New source: write a `fetch_x() -> list[Job]`, register in `FETCHERS`,
  add to `sources.enabled`.
- Different note model: point `[ollama]` at any OpenAI-ish local endpoint,
  or swap `draft_note()` for a LiteLLM call if you want Claude drafting them.
- Tracker: `state.db` is plain SQLite — join your own outreach tracking
  tables onto `queued_companies` if you want reply/follow-up tracking later.
