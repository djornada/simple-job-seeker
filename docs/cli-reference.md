# CLI reference

[← Docs home](README.md)

Everything the web UI does is also available from the terminal. All three
tools share the same `state.db`, so you can mix and match freely.

- [`queue_agent.py`](#queue_agentpy) — build the daily queue
- [`tracker.py`](#trackerpy) — log and track outreach
- [`profile.py`](#profilepy) — import your résumé
- [`install.sh`](#installsh) — set up a local Ollama model
- [`webapp.py`](#webapppy) — the web UI

---

## queue_agent.py

Build today's queue: fetch, score, filter, dedupe, and emit.

```bash
python queue_agent.py [--notes] [--dry-run] [--stats] [-n N]
```

| Flag | Effect |
| --- | --- |
| `--notes` | Also draft a sub-200-char connection note per target via Ollama. |
| `--dry-run` | Print the queue but persist nothing (no `state.db` writes, no file). |
| `--stats` | Print pipeline stats (jobs seen, companies queued, most-queued) and exit. |
| `-n N` | Override `[targets] per_day` for this run. |

On a normal run it prints the queue, writes `queues/<date>.md`, and records
state. Examples:

```bash
python queue_agent.py                # today's queue, persisted
python queue_agent.py --notes        # ...with drafted connection notes
python queue_agent.py -n 5 --dry-run # preview 5 targets, change nothing
python queue_agent.py --stats        # just the numbers
```

A dead job board logs a warning and is skipped — it never kills the run.

---

## tracker.py

Log every touchpoint; never lose a follow-up.

```bash
python tracker.py add <company> [--person NAME] [--action A] [--note TEXT] [--followup DAYS]
python tracker.py due
python tracker.py done <id>
python tracker.py board
python tracker.py history <company>
```

**Actions** (the funnel, in order):
`visited`, `connected`, `messaged`, `replied`, `meeting`, `applied`,
`rejected`, `offer`. Default is `visited`.

| Command | What it does |
| --- | --- |
| `add` | Log an interaction. `--followup DAYS` schedules a follow-up. |
| `due` | List follow-ups due or overdue. |
| `done <id>` | Close a follow-up by its id (shown in `due`). |
| `board` | Pipeline overview — each company by its furthest stage. |
| `history <company>` | Full timeline for one company. |

**Company name resolution:** names resolve by prefix when unambiguous —
`Acme` becomes `Acme Corp` if that's the only match. Examples:

```bash
python tracker.py add "Acme Corp" --person "Jane Doe" --action connected --followup 5
python tracker.py add Acme --action replied --note "asked for my CV" --followup 2
python tracker.py due
python tracker.py done 3
python tracker.py board
python tracker.py history Acme
```

---

## profile.py

Import your LinkedIn résumé so the queue ranks by real fit and notes reference
your actual experience.

```bash
python profile.py import <export.zip>
python profile.py show
```

| Command | What it does |
| --- | --- |
| `import <export.zip>` | Read a LinkedIn data-export ZIP from local disk, build a compact profile, and store it in `state.db`. |
| `show` | Print the stored profile — headline, skills, positions, import date. |

```bash
python profile.py import ~/Downloads/Complete_LinkedInDataExport.zip
python profile.py show
```

The ZIP is read locally only — nothing is sent to LinkedIn. Where to get it
and what it changes: [Résumé matching](resume-matching.md).

---

## install.sh

One-shot setup for the optional AI features.

```bash
./install.sh
```

It ensures Ollama is installed, detects your GPU VRAM (`nvidia-smi`, or the
amdgpu sysfs for AMD cards), picks a `qwen3` model from a size ladder that
fits your card, pulls it, and updates `[ollama] model` in `config.toml`.
Only needed if you want drafted notes or the résumé re-rank.

---

## webapp.py

Serve the local web UI.

```bash
python webapp.py
```

Binds to `[web] host`:`[web] port` (default `127.0.0.1:3000`). Full tour:
[Web UI guide](web-ui.md).

---

See also: [Configuration](configuration.md) for every setting these tools read.
