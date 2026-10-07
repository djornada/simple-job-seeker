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
3. Drops non-Brazil-friendly locations (`brazil_friendly_only`) and,
   with `[gates]` set, postings you can't be hired for (language,
   citizenship, region-only)
4. Skips jobs already seen and companies queued in the last 30 days (SQLite)
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
  UI's `/board`, `/company` and `/stats` include it.
- Stale rules live in `config.toml`'s `[applications]`. "Quiet" counts
  days since the last status change or follow-up:
  - `followup_after_days` (10): `stale` and the web UI's `/due` suggest a
    follow-up…
  - `max_followups` (2): …until you've recorded this many.
  - `no_response_after_days` (60): `sweep` offers to close it as
    `no_response`, and only moves anything after you confirm.

In the web UI: an **I applied** button on each queue card creates the
application from that job (company, title, URL). `/applications` lists
them by status, with forms to move one along or record a follow-up, plus
a form for roles you applied to outside the queue. `/due` shows a "gone
quiet" section and the two-step no-response sweep, and quiet applications
count toward the Due tab's badge.

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
- `[gates]` — reject postings you can't be hired for, before any LLM call.
  Delete the table to turn them off. Each build prints
  `[gate] rejected N (language X, eligibility Y)` to stderr.
  - `languages` — languages you work in, with your level (`A1`–`C2` or
    `"native"`). A posting that requires one you haven't listed ("fluent in
    German", "German (C1)", "German speaker", "German is required") is
    rejected; "German or English" passes if either is listed. Asking for a
    higher level than yours ("native English" vs your `C1`) only adds a
    flag. A mention softened nearby ("a plus", "nice to have", "preferred")
    never rejects. Only human languages count, so "Go" or "Rust" never
    trigger it. Leave it empty to turn the language gate off.
  - `eligibility_blockers` — phrases in the posting text that reject it
    ("us citizen", "security clearance"…).
  - `region_only` — phrases in the location or title that reject it
    ("us only", "remote (us)"…), even when the location also says remote.

  Phrases are case-insensitive and match at a word start, so `us citizen`
  also catches "US citizens". Flags show as chips on the web UI's queue
  cards, as a `Flags:` line in `queues/<date>.md` and in the extension
  popup, which also shows why a skipped item was rejected.

## Extending

- New source: write a `fetch_x() -> list[Job]`, register in `FETCHERS`,
  add to `sources.enabled`.
- Different note model: point `[ollama]` at any OpenAI-ish local endpoint,
  or swap `draft_note()` for a LiteLLM call if you want Claude drafting them.
- Tracker: `state.db` is plain SQLite — join your own outreach tracking
  tables onto `queued_companies` if you want reply/follow-up tracking later.

## Browser extension

`../extension/` is a Chrome extension that reads whatever's on screen on
the LinkedIn feed or a Jobs page (on a manual click, nothing automatic)
and POSTs it to this server's `/api/rate` for scoring against the same
filters/résumé fit used above. Set `[extension].token` in `config.toml`
to enable it — see `extension/README.md` for setup.
