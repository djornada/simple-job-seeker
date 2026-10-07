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

Six tabs across the top: **Queue · Board · Due · Log · Stats · Résumé**. The
**Due** tab shows a badge with the number of follow-ups that need attention.

---

## Queue

Your daily worklist and the page you'll live in.

- **Build today's queue** runs the full pipeline in the background (the page
  keeps working while it fetches). If today's queue already exists, the button
  reads **Fetch more targets** and tops it up.
- Tick **draft notes** before building to also generate connection notes.
- A **progress bar** shows how many targets you've worked (`3/10 worked`).
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

If your résumé is imported, the card also shows a **fit note** (`fit 8/10 —
why it fits / what to emphasize`).

**Connection notes:** click **Draft connection note** to have the local model
write one (it appears with a live character count, capped at 200). Notes draft
in the background — the card shows "drafting note…" until it's ready.

**Keyword coverage:** with a saved posting and an imported résumé, click
**Check keywords** to list the skills the posting asks for and whether your
résumé covers them (`covered`, `synonym`, `missing`), missing required ones
first. It runs in the background like a note draft ("checking keywords…"),
then shows the table in place. See
[Résumé matching](resume-matching.md#4-keyword-coverage-per-posting).

**The tick box** on the left marks the target *worked* — see
[Concepts → The checkbox](concepts.md#the-checkbox). The loop:

> visit 2–3 profiles → connect with the note → tick it off.

---

## Board

Your pipeline at a glance. Every company you've logged, grouped by the
**furthest stage** it has reached (offer at the top, visited at the bottom).
Click any company to open its [timeline](#company-timeline).

Empty until you [log](#log) your first touchpoint.

---

## Due

Follow-ups that are **due or overdue**, oldest first, each tagged if overdue.
When you've done the follow-up, hit **Close** to clear it. This is your "don't
let anything slip" list — the tab badge counts what's waiting.

---

## Log

Record a touchpoint. Pick the **company** (autocompletes from companies you've
queued or contacted), optionally **who** you spoke with, the **action**
(`visited`, `connected`, `messaged`, `replied`, `meeting`, `applied`,
`rejected`, `offer`), an optional **follow-up in N days**, and a **note** for
future-you. Recent activity is listed below the form.

Logging here is what powers the Board, Due, and Stats views.

---

## Company timeline

Reached by clicking a company anywhere in the app. Shows how many times it's
been queued and the full chronological history of your outreach, plus a
shortcut to log a new touchpoint against it.

---

## Stats

Source-effectiveness reporting, so you can see which boards actually convert.

- **By source** — for each job board: how many companies you queued, how many
  you contacted, how many replied, and the reply rate.
- **By fit-score band** — once you've imported a résumé and accumulated some
  LLM-scored history, the same conversion funnel broken down by fit score
  (9–10, 7–8, 5–6, 0–4).

Companies are matched between the queue and the outreach log by name (loose,
case-insensitive) — fine for personal use; the page states the caveat.

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
