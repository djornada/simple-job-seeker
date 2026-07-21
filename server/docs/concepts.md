# Concepts

[← Docs home](README.md)

The whole tool rests on a few small ideas. Once these click, everything else
is detail.

## The human-click principle

The tool **decides** and **prepares**; you **act**. It picks the companies,
scores them, and builds the exact search links you'd otherwise assemble by
hand — but it never opens LinkedIn, never visits a profile, never sends a
request. Every outbound action is a link *you* click in *your own* browser.

This isn't a limitation to work around; it's the point. Programmatic LinkedIn
activity gets accounts banned. Keeping the human in the loop is what makes the
tool safe to run every day.

## Targets, not jobs

The unit of work is a **target**: one company worth reaching out to today.

The pipeline reads many individual job posts, but it collapses them — **one
row per company** — because your goal is to connect with people at a company,
not to apply to a specific listing. A company you worked recently won't come
back for a while (`company_cooldown_days`), so you're not pestering the same
place twice.

## The daily queue

Each day you **build a queue**. The pipeline:

1. **Fetches** roles from the enabled [job sources](architecture.md#sources).
2. **Scores** each by keyword (see below) and drops the ones that don't match.
3. **Filters** by hiring region if `brazil_friendly_only` is on.
4. **Dedupes** to one company per row and skips companies still on cooldown.
5. **Ranks** — and if your résumé is imported, re-ranks by real fit with a
   local LLM.
6. **Caps** the result at `per_day` (default 10) so the list stays doable.

Each row arrives with everything you need to act: the job post link, LinkedIn
people-search links for recruiters and engineering managers at that company, a
Google x-ray link, and — optionally — a fit note and a drafted connection note.

## How scoring works

Two stages, the second optional:

**1. Keyword gate (always on).** Defined in `[filters]`:
- A **role keyword** must appear in the job *title* (e.g. `senior`,
  `frontend`, `full stack`). No role match → the job is rejected outright.
  Each match adds points.
- **Stack keywords** found in the title or tags (e.g. `react`, `typescript`,
  `node`) each add a smaller amount.
- **Exclude keywords** in the title reject the job (e.g. `junior`, `php`,
  `recruiter`).

**2. Résumé re-rank (on when a profile is imported).** The top of the
keyword-ranked list is sent to a local LLM, one job at a time, together with
your résumé. The model returns a 0–10 fit score and a one-line "why it fits /
what to emphasize" note. The queue is then ordered by that score, and jobs
below `min_llm_score` are dropped. If no résumé is imported or Ollama is down,
this stage is skipped entirely and you get the keyword ranking.

Details: [Résumé matching](resume-matching.md).

## The checkbox

Every queue card has a **tick box**. It means exactly one thing:

> **"I've worked this target today."**

Ticking it dims the card, strikes through the company name, and fills the
progress bar at the top (`3/10 worked`). It's local batch-hygiene — a way to
keep your place so you can stop and resume without re-reading the whole list.
It records nothing about the *outcome* of your outreach.

The intended loop per target:

> **visit 2–3 profiles → send a connection request (paste the note) → tick it off**

## The outreach pipeline (the tracker)

The checkbox handles *today*. The **tracker** handles the *relationship over
time*. Whenever outreach turns into something real, you **log** it with an
action:

`visited → connected → messaged → replied → meeting → applied → rejected → offer`

Logging can also schedule a **follow-up** in N days. From that log the tool
derives three views:

- **Board** — every company grouped by the furthest stage it's reached.
- **Due** — follow-ups that are due or overdue, ready to close.
- **History** — the full timeline for one company.

### Checkbox vs. logging — the key distinction

| | The queue checkbox | Logging a touchpoint |
| --- | --- | --- |
| **Answers** | "Did I handle this row today?" | "What's happening with this company?" |
| **Lifespan** | Per-day, ephemeral | Durable, permanent history |
| **Feeds** | Today's progress bar | Board, Due, History, and `/stats` |

So: **tick the box** to clear a target from today's list; **log** it if the
conversation actually started. One keeps your day moving, the other keeps your
memory.

---

Next: [Web UI guide](web-ui.md) or the [CLI reference](cli-reference.md).
