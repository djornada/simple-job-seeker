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
python -m profile import ~/Downloads/Complete_LinkedInDataExport.zip
python -m profile show     # review what was stored
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

After the usual keyword gate, the top keyword-ranked jobs are sent to your
local model **one at a time**, each paired with your profile: 1.5 ×
`[targets] per_day` of them (45 for a queue of 30), or `[resume] shortlist`
if that's more. The extra half covers the jobs `min_llm_score` drops.
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

Notes are written in your voice, to the recruiter or engineering manager you
look up through the card's links (`[targets] people_roles`), whose name you
don't know yet. Two short sentences: the role and company first, then one
concrete result of yours that fits. No names at all, no signature. The code
enforces what the model can get wrong: a named greeting ("Hi Sam,") becomes
"Hi,", a sign-off is dropped, and a draft over 200 characters gets one retry
and is then cut at its last full sentence, never mid-word.

### 3. Stats gain a fit-score breakdown

The [Stats](web-ui.md#stats) page adds a conversion funnel by fit-score band
once you've accumulated enough scored history.

### 4. Keyword coverage per posting

Each queue card with a saved posting gets a **Check keywords** button. One
model call reads the posting and lists the skills it asks for, split into
**required** and **preferred** (preferred is only what the posting marks as
optional: "nice to have", "a plus", "bonus"). Each term is then checked
against your profile text, without the model:

| Status | Meaning |
| --- | --- |
| `covered` | The term appears in your profile as a whole word, as the posting spells it. |
| `synonym` | It appears under another spelling from [`[keywords.aliases]`](configuration.md#keywordsaliases), e.g. the posting says `k8s` and your profile says `Kubernetes`. |
| `missing` | Neither. |

Missing required terms are listed first. The card's summary line counts
what's matched (`3/5 required, 1/4 preferred`), and **Check again** re-runs
it, for example after re-importing your résumé or adding an alias.

The model only *extracts* terms; matching is plain text search, so the same
keyword list always gives the same result. A term the model returns that
doesn't appear anywhere in the posting is dropped, so it can't invent
requirements. Checks run on demand, never during a build, so builds stay
fast. The result is saved in `queue_items.coverage_json`.

## Graceful degradation

This whole layer is optional and fails soft:

- **No résumé imported** → the pipeline behaves exactly as the keyword-only
  version.
- **Ollama not running / unreachable** → the re-rank stage is skipped and you
  get the keyword ranking, with no errors. A keyword check shows "keyword
  check failed" with a **Try again** button; the rest of the card works.
- **No saved posting or no résumé** → the card has no **Check keywords**
  button.

So you can import a résumé and still run without a model, or run a model
without a résumé — each feature stands on its own.

## Refreshing

Re-import any time (upload again, or re-run `python -m profile import`). The new
profile replaces the old one.

## Configuration

The two knobs live in `[resume]`:

```toml
[resume]
shortlist = 30       # min jobs sent to the LLM re-rank after the keyword gate
min_llm_score = 5    # drop jobs the model scores below this (0 disables)
```

See [Configuration](configuration.md#resume) for context, and
[Concepts → How scoring works](concepts.md#how-scoring-works) for where this
fits in the pipeline.
