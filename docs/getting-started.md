# Getting started

[← Docs home](README.md)

This gets you from a fresh clone to your first daily queue in a few minutes.

## Requirements

- **Python 3.11+** (the tool uses `tomllib`; it runs happily on 3.14).
- **No pip installs.** Everything runs on the Python standard library.
- **Optional: [Ollama](https://ollama.com)** running locally — only needed for
  the AI features (draft connection notes and the résumé-based re-rank).
  Without it, everything else works; those features simply switch off.

## 1. Get the code

```bash
git clone <your-repo-url> simple-job-seeker
cd simple-job-seeker
```

Nothing to build or install.

## 2. Configure

All settings live in [`config.toml`](configuration.md). The shipped defaults
are tuned for a senior full-stack profile hiring from Brazil. At minimum, open
it and adjust:

- `[filters] role_keywords / stack_keywords / exclude_keywords` — the words
  that define which roles match you.
- `[filters] brazil_friendly_only` — set `false` if you don't need the
  hiring-region filter.
- `[targets] per_day` — how many companies you want to work each day.

Full walkthrough: [Configuration](configuration.md).

## 3. Build your first queue

### From the terminal

```bash
python queue_agent.py
```

This fetches the enabled job boards, scores and filters roles, dedupes to one
company per row, and prints today's queue. It also saves it to `queues/<date>.md`
and records state in `state.db`.

Useful flags (full list in the [CLI reference](cli-reference.md)):

```bash
python queue_agent.py --dry-run   # print, but don't persist anything
python queue_agent.py -n 5        # just 5 targets today
python queue_agent.py --stats     # pipeline stats, then exit
```

### From the web UI

```bash
python -m webapp
```

Open the printed address (by default **http://127.0.0.1:3000**) and click
**Build today's queue**. This is the recommended way to actually *work* the
queue — see the [Web UI guide](web-ui.md).

## 4. (Optional) Turn on the AI features

The draft-notes and résumé re-rank features need a local model.

```bash
./install.sh
```

`install.sh` makes sure Ollama is installed, detects your GPU's VRAM, picks a
`qwen3` model that fits, pulls it, and writes the choice into
`[ollama] model` in `config.toml`. Then:

```bash
python queue_agent.py --notes     # also draft connection notes
```

or tick **draft notes** before building in the web UI.

## 5. (Optional) Put your résumé in the loop

Import your LinkedIn data export and the queue starts ranking by *real fit*,
not just keywords, and connection notes reference your actual experience.

- Web: open the **Résumé** tab and upload the ZIP.
- CLI: `python -m profile import ~/Downloads/YourExport.zip`

Details and how to get the ZIP: [Résumé matching](resume-matching.md).

## 6. (Optional) Run it daily

`queue_agent.py` is a natural cron job. For example, weekdays at 8am:

```cron
0 8 * * 1-5  cd /path/to/simple-job-seeker && /usr/bin/python3 queue_agent.py --notes >> cron.log 2>&1
```

Then just open the web UI whenever you sit down to work the list.

## What lands on disk

- `state.db` — SQLite; jobs seen, companies queued, queue items, your résumé,
  and the outreach log.
- `queues/<date>.md` — a markdown copy of each day's queue.
- `cron.log` — if you schedule it.

All three are **gitignored** — they hold data about real people. See
[Architecture → Privacy by design](architecture.md#privacy-by-design).

---

Next: [Concepts](concepts.md) — how the queue and the tracker actually work.
