# Web UI guide

[← Docs home](README.md)

The web UI is the recommended way to work your queue day to day. It's a small,
local-only app over the same `state.db` the CLIs use.

```bash
python -m webapp
```

By default it serves on **http://127.0.0.1:3000** (host/port come from
`[web]` in [`config.toml`](configuration.md)). It **binds to localhost on
purpose** — `state.db` holds data about real people, so it's never exposed to
your network.

The server is pure standard library (`http.server` + `sqlite3`); the only
client-side script is [htmx](https://htmx.org), vendored locally (never a
CDN) so ticking a target, drafting a note, or building the queue updates in
place instead of reloading the page. Like everything here, it only
generates links. The click is still human.

## Navigation

Tabs across the top: **Queue · Board · Applications · Stats · Résumé**.
The **Board** tab shows a badge with the number of things that need
attention: follow-ups due and applications gone quiet.

---

## Queue

Your daily worklist and the page you'll live in.

- **Build today's queue** runs the full pipeline in the background (the page
  keeps working while it fetches). The banner shows where it is: fetching
  job boards, then `scoring fit 12/45` while the résumé re-rank runs (one LLM
  call per job, so a queue of 30 takes a few minutes). If today's queue
  already exists, the button reads **Fetch more targets** and tops it up.
- Tick **draft notes** before building to also generate connection notes
  (one more LLM call per target; you can draft per card instead).
- A **progress bar** shows how many targets you've worked (`3/30 worked`).
  Ticking a card collapses it to one line (company and title); untick it to
  see the rest again.
- A **date strip** appears once you have history, so you can revisit earlier
  days.
- The **résumé indicator** by the date links to the [Résumé](#résumé) tab and
  shows whether a profile is imported.

### Working a target card

Each card shows the **company**, a keyword-score badge, a meta line
(title · location · source), and a row of links:

- **job post** — the original listing.
- **LinkedIn · <role>** — a people search for each role in
  `[targets] people_roles` (e.g. Technical Recruiter, Engineering Manager) at
  that company.
- **Google x-ray** — a `site:linkedin.com/in` search as a fallback.
- **Log** — opens the [log dialog](#logging-a-touchpoint) with the company
  filled in.

If your résumé is imported, the card also shows a **fit note** (`fit 8/10 —
why it fits / what to emphasize`).

**Connection notes:** click **Draft connection note** to have the local model
write one (it appears with a live character count, capped at 200). Notes draft
in the background — the card shows "drafting note…" until it's ready. Click
**Redraft** under a note to replace it; if the redraft fails, the old note
stays. See [Résumé matching](resume-matching.md#2-connection-notes-get-personal)
for how notes are written.

**Keyword coverage:** with a saved posting and an imported résumé, click
**Check keywords** to list the skills the posting asks for and whether your
résumé covers them (`covered`, `synonym`, `missing`), missing required ones
first. It runs in the background like a note draft ("checking keywords…"),
then shows the table in place. See
[Résumé matching](resume-matching.md#4-keyword-coverage-per-posting).

**The tick box** on the left marks the target *worked* — see
[Concepts → The checkbox](concepts.md#the-checkbox). The loop:

> visit 2–3 profiles → connect with the note → tick it off.

Ticking a card also offers to log it: the [log dialog](#logging-a-touchpoint)
opens with the company and `connected` filled in. **Log touchpoint** saves it
and keeps you on the queue; **Cancel** or Esc keeps the tick and logs
nothing. It doesn't ask when you untick, or when the company already has a
touchpoint today. Without JavaScript, ticking just ticks.

---

## Board

Your pipeline at a glance. On top, a [due](#due) section when something
needs you. Below it, every company you've logged, grouped by its **latest
stage** (offer at the top, visited at the bottom). Each row shows the date
of the last touch, the company, and its status; click it to expand the
company's full timeline: how many times it's been queued, then every
touchpoint in order. A company name anywhere else in the app (the due
section, Applications, skill gaps on Stats, recent activity) opens its row
here.

**Recent activity**, collapsed at the bottom, lists the last 25 touchpoints
across all companies.

Empty until you log your first touchpoint.

### Logging a touchpoint

**Log touchpoint** in the Board header opens a dialog over the page. The
same dialog opens from **Log touchpoint** inside an expanded row and from
**Log** on a queue card, with the company filled in. Pick the **company**
(autocompletes from companies you've queued or contacted), optionally
**who** you spoke with, the **action** (`visited`, `connected`, `messaged`,
`replied`, `meeting`, `applied`, `rejected`, `offer`), an optional
**follow-up in N days**, and a **note** for future-you.

Saving lands on Board with that company's row expanded (except from a
ticked card's prompt, which keeps you on the queue). **Cancel** or Esc
closes the dialog without saving. Without JavaScript the buttons open
`/board?log=<company>` with the form already showing.

Logging is what powers Board and Stats. Old `/log` and `/company?name=`
links redirect to Board.

### Due

The "don't let anything slip" list, at the top of Board and only when
something is waiting (the Board tab's badge counts it):

- **Follow-ups** due or overdue, oldest first, each tagged if overdue. When
  you've done the follow-up, hit **Close** to clear it.
- **Gone quiet — follow up:** applications quiet long enough to nudge. Write
  the follow-up yourself, then hit **Followed up** to reset the clock.
- **Quiet N+ days — no response?** Applications quiet too long. **Mark as no
  response…** only shows a confirm step; nothing moves until you hit
  **Confirm**.

Every button lands back on Board. Old `/due` links redirect there.

---

## Stats

How the search is going: which boards actually convert, and which skills keep
coming up missing.

- **By source** — for each job board: how many companies you queued, how many
  you contacted, how many replied, and the reply rate.
- **By fit-score band** — once you've imported a résumé and accumulated some
  LLM-scored history, the same conversion funnel broken down by fit score
  (9–10, 7–8, 5–6, 0–4).

Companies are matched between the queue and the outreach log by name (loose,
case-insensitive) — fine for personal use; the page states the caveat.

### Skill gaps

Below the tables, the skills your résumé fit keeps flagging as missing,
added up across postings over the **last 30 or 90 days, or all time** (the
switch reloads Stats at this section; 90 days by default). Each row shows
how many postings flagged the skill, a weighted score that counts gaps from
weaker fits more (sum of 1 − overall fit/100), when it was last seen, and up
to three example companies, each opening its Board row. Skills already in
your imported profile are left out; merge spellings with
[`[keywords.aliases]`](configuration.md). Old `/gaps` links redirect here.

---

## Résumé

Import and review your LinkedIn profile.

- **Before import:** an upload form plus a short guide on where to get the ZIP
  from LinkedIn.
- **Upload** the LinkedIn data-export `.zip` and it's parsed locally (nothing
  is sent to LinkedIn) and stored in `state.db`. A success or error banner
  confirms the result.
- **After import:** your headline, skills, import date, and the exact profile
  text that feeds the re-rank and note drafting — plus a re-import form to
  refresh it.

Full details, including how the import feeds ranking and notes:
[Résumé matching](resume-matching.md).

---

## A note on safety

Every form in the app is same-origin protected (cross-origin POSTs are
rejected), and the server only ever binds to localhost. It renders links; it
never acts on LinkedIn for you.

---

Prefer the terminal? See the [CLI reference](cli-reference.md).
