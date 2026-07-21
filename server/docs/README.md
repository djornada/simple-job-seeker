# simple-job-seeker

**A personal, self-hosted assistant for a remote job search.**

simple-job-seeker turns the daily grind of a job hunt into a short, decided
checklist. Every morning it pulls fresh roles from remote job boards, ranks
them against what you're actually looking for (and, optionally, your real
résumé), and hands you a small queue of companies to reach out to — each one
pre-loaded with the search links you need. You do the clicking; the tool does
the deciding.

It also remembers everyone you've talked to, so no follow-up ever falls
through the cracks.

## The one non-negotiable

**Nothing touches LinkedIn programmatically.** No scraping, no automated
visits, no auto-connect. The tool decides targets and generates links — the
click is always human. This is what keeps your account safe from bans, and
it's a design constraint, not a preference. See
[Architecture → Privacy by design](architecture.md#privacy-by-design).

## Who it's for

Someone running their own remote job search who wants to work a steady,
deliberate pipeline instead of doom-scrolling job boards — and who is
comfortable running a couple of Python scripts locally. It ships tuned for a
senior full-stack profile (React/Node, hiring-from-Brazil location filter),
but every knob is in one config file.

## What you get

- **A daily queue** of companies worth contacting, capped so it stays doable.
- **Smart ranking** — keyword scoring, plus an optional local-LLM re-rank
  against your imported résumé ("why this fits / what to emphasize").
- **Pre-built outreach links** per target: the job post, LinkedIn people
  searches for recruiters/EMs, and a Google x-ray.
- **Draft connection notes** (under 200 chars) written by a local model.
- **An outreach tracker** — log every touchpoint, never miss a follow-up.
- **A local web UI** for the whole thing, plus CLIs if you prefer the
  terminal.
- **Runs entirely on your machine.** Pure Python standard library; an
  optional local [Ollama](https://ollama.com) model powers the AI bits.

## Documentation

| Doc | What's in it |
| --- | --- |
| [Getting started](getting-started.md) | Requirements, setup, your first queue |
| [Concepts](concepts.md) | The mental model: queue, targets, the checkbox, the pipeline |
| [Web UI guide](web-ui.md) | Every page, button, and workflow |
| [CLI reference](cli-reference.md) | `queue_agent.py`, `tracker.py`, `profile`, `install.sh` |
| [Résumé matching](resume-matching.md) | Import your résumé, re-rank, personalize notes |
| [Configuration](configuration.md) | Every setting in `config.toml` |
| [Architecture](architecture.md) | Components, data model, sources, privacy design |

New here? Start with [Getting started](getting-started.md), then skim
[Concepts](concepts.md).
