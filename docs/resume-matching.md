# Résumé matching

[← Docs home](README.md)

By default the queue ranks roles by keyword overlap. Import your résumé and it
starts ranking by **real fit** — a local LLM scores each shortlisted job
against your actual experience — and your connection notes start referencing
who you really are.

Everything here runs locally. The résumé is a **manual** download you provide;
nothing ever talks to LinkedIn.

## Getting your LinkedIn export

1. On LinkedIn: **Settings & Privacy → Data Privacy → Get a copy of your data**.
2. Choose the **larger archive** (the one that includes Profile, Positions,
   and Skills — not just "articles/activity").
3. LinkedIn emails you a download link, usually within minutes. Save the ZIP.

## Importing it

**Web UI:** open the **Résumé** tab and upload the ZIP. A banner confirms
success (or explains what went wrong).

**CLI:**

```bash
python profile.py import ~/Downloads/Complete_LinkedInDataExport.zip
python profile.py show     # review what was stored
```

### What gets read

The importer opens the ZIP and locates `Profile.csv`, `Positions.csv`, and
`Skills.csv` by name (export layouts vary, so it matches case-insensitively
and defensively by column header). From them it builds a **full profile**:
your headline, summary, **every** position (title @ company, dates, and the
complete description — untruncated), and your full skills list. That assembled
text — not the raw files — is what the model sees, both for the re-rank and
for drafting connection notes.

It's stored in the `profile` table of `state.db` (a single row), which is
gitignored like the rest of your data.

## What changes once it's imported

### 1. The queue re-ranks by fit

After the usual keyword gate, the top `[resume] shortlist` jobs (default 30)
are sent to your local model **one at a time**, each paired with your profile.
The model replies with:

```json
{"score": 0-10, "fit": "one line: why it fits / what to emphasize"}
```

The queue is then ordered by that fit score (keyword score breaks ties), and
any job scoring below `[resume] min_llm_score` (default 5; set `0` to disable
the floor) is dropped. The fit line shows up on each queue card and in the
saved markdown.

### 2. Connection notes get personal

The draft-note prompt swaps its generic "senior engineer" description for your
real headline, skills, and full experience, so notes are grounded in your
actual background — the model can reference a role or project that fits.

### 3. Stats gain a fit-score breakdown

The [Stats](web-ui.md#stats) page adds a conversion funnel by fit-score band
once you've accumulated enough scored history.

## Graceful degradation

This whole layer is optional and fails soft:

- **No résumé imported** → the pipeline behaves exactly as the keyword-only
  version.
- **Ollama not running / unreachable** → the re-rank stage is skipped and you
  get the keyword ranking, with no errors.

So you can import a résumé and still run without a model, or run a model
without a résumé — each feature stands on its own.

## Refreshing

Re-import any time (upload again, or re-run `profile.py import`). The new
profile replaces the old one.

## Configuration

The two knobs live in `[resume]`:

```toml
[resume]
shortlist = 30       # jobs sent to the LLM re-rank after the keyword gate
min_llm_score = 5    # drop jobs the model scores below this (0 disables)
```

See [Configuration](configuration.md#resume) for context, and
[Concepts → How scoring works](concepts.md#how-scoring-works) for where this
fits in the pipeline.
