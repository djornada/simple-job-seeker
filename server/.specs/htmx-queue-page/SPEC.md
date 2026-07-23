# Spec: htmx on the daily-queue page

Status: draft
Date: 2026-07-23

## 1. Problem

The web UI (`server/webapp/`) is a pure-stdlib `http.server` app (no
Flask, no Jinja2, no JS) — a deliberate choice per `server/CLAUDE.md`
("pure stdlib, no dependencies", "surgical edits, no rewrites"). Every
interaction on the daily-queue page (`/`) causes either a full-page reload
(toggling a target, submitting the build form) or blanket
`<meta http-equiv="refresh" content="3">` polling (`layout.py`'s `page()`,
`refresh=` param) while a build runs or a note is drafting. The
meta-refresh reloads the *entire* page every 3 seconds for the duration of
any background work, which is the main usability papercut in an otherwise
solid small tool.

A full migration to a SPA (React/Vue) or SSR framework (Nuxt) was
considered and rejected as disproportionate: the current UI is ~1,100
lines across 16 files with 7 routes and no complex client state — a
framework migration would mean adopting an npm/Node toolchain and
rewriting every page module to fix what's really a page-reload problem.

## 2. Goal

Add **htmx** to the `/` page to replace full-page reloads and blanket
polling with in-place, scoped DOM updates, while keeping the server 100%
Python and the page 100% server-rendered. Concretely:

1. Toggling a queue item updates just that card, no navigation.
2. Drafting a connection note shows "pending" immediately and swaps in the
   finished note (or failure state) via a poll scoped to that one item —
   not the whole page.
3. Running a build updates just the banner/progress section via a scoped
   poll, not the whole page.
4. The old blanket `<meta refresh>` mechanism is removed once nothing
   depends on it.

Out of scope: every other page (`/board`, `/due`, `/log`, `/company`,
`/stats`, `/profile`). Their POST forms (`/add`, `/done`) navigate to a
different page after submit, so a full reload there isn't a real papercut.

## 3. Non-negotiables

- **Pure stdlib on the Python side, no new Python dependencies.** htmx is
  a client-side `.js` file only; nothing changes about how `server.py`
  runs.
- **No CDN.** The webapp binds only to `127.0.0.1` and has never made an
  external network call from the browser. htmx must be vendored (checked
  into the repo, served locally), not loaded from a third-party host.
- **Surgical, not a rewrite.** Existing `<form method="post" action="...">`
  submissions keep working unmodified as a no-JS fallback; htmx attributes
  are additive. Scope is limited to `/` — do not touch other pages beyond
  the one shared `<script>` include in `layout.py`.
- **`origin_ok()`'s same-origin POST check is unchanged.** htmx's
  `hx-post` on a `<form>` still fires as a same-origin `fetch()` with
  normal `Origin` header behavior and the default
  `application/x-www-form-urlencoded` body, so the existing CSRF check and
  `urllib.parse.parse_qs(raw.decode())` parsing keep working untouched.

## 4. Components

### 4.1 Vendored htmx asset

- New file `server/webapp/static/htmx.min.js` — a pinned htmx 2.0.x
  release (BSD-2-Clause), downloaded once and committed (no npm in this
  repo to automate it).
- `assets.py`: add `HTMX_JS = (BASE_DIR / "webapp" / "static" /
  "htmx.min.js").read_bytes()`, same read-once-at-import pattern as
  `FAVICON`.
- `server.py`'s `do_GET`: add a `/static/htmx.min.js` branch mirroring the
  existing `/favicon.ico` branch, served via the existing `send_bytes()`
  helper (`text/javascript`, already sets `Cache-Control: max-age=86400`).
- `layout.py`: add `<script src="/static/htmx.min.js"></script>` to
  `page()`'s `<head>` block, next to `<style>{CSS}</style>` — applies to
  every page via the shared shell.

### 4.2 Extract the per-item fragment (`pages/queue.py`)

`page_queue` currently builds each `<article class="target">` inline in a
loop. Extract it verbatim into:

```python
def render_item(r: sqlite3.Row, date: str, cfg: dict, pending: bool,
                failed: bool) -> str:
    ...  # today's per-item body, unchanged
```

`page_queue`'s loop becomes `[render_item(r, date, cfg, r["uid"] in
pending, r["uid"] in failed) for r in rows]`. This step should produce
byte-identical HTML to today — a pure refactor, verified before any
behavioral change.

`Job.uid` (`sources/base.py`) is `f"{source}:{url}"`, which contains `:`
and `/` — illegal in a CSS id selector. So item-scoped htmx targeting uses
`hx-target="closest article"` (walk up from the triggering element), never
an id built from uid.

### 4.3 Toggle → in-place swap

Toggle `<form>` in `render_item` gains `hx-post="/toggle" hx-target="closest
article" hx-swap="outerHTML"` alongside the existing `method="post"
action="/toggle"`. `outerHTML` (not `innerHTML`) because the done/not-done
class lives on the `<article>` itself.

`server.py`'s `post_toggle`:

```python
def post_toggle(self, form):
    date, uid = form.get("date", [""])[0], form.get("uid", [""])[0]
    conn = db()
    conn.execute("UPDATE queue_items SET done = 1 - done WHERE date = ? AND uid = ?",
                 (date, uid))
    conn.commit()
    row = conn.execute("SELECT * FROM queue_items WHERE date = ? AND uid = ?",
                       (date, uid)).fetchone()
    conn.close()
    if row is None:
        self.send_error(HTTPStatus.NOT_FOUND); return
    if self.headers.get("HX-Request") == "true":
        with NOTES_LOCK:
            pending, failed = uid in NOTES_PENDING, uid in NOTES_FAILED
        self.respond(render_item(row, date, load_config(), pending, failed))
    else:
        self.redirect(f"/?date={urllib.parse.quote(date)}")
```

`HX-Request` picks response *shape* only (fragment vs. redirect) — not a
security check, `origin_ok()` still runs first as today.

### 4.4 Note drafting → scoped poll

Factor the note's three-way HTML (existing note / pending / draft-or-retry
button) into its own helper:

```python
def note_block(date: str, uid: str, note: str | None, pending: bool,
               failed: bool) -> str:
    ...  # today's three branches, verbatim
    poll = (f' hx-get="/note-status?{urllib.parse.urlencode({"date": date, "uid": uid})}"'
            ' hx-trigger="every 3s" hx-swap="outerHTML"') if pending else ""
    return f'<div class="notewrap"{poll}>{inner}</div>'
```

`render_item` calls `note_block(date, r["uid"], r["note"], pending,
failed)` instead of building the note HTML inline.

New route:

```python
def get_note_status(params: dict[str, list[str]]) -> str:
    date, uid = params.get("date", [""])[0], params.get("uid", [""])[0]
    conn = db()
    row = conn.execute("SELECT note FROM queue_items WHERE date = ? AND uid = ?",
                       (date, uid)).fetchone()
    conn.close()
    if row is None:
        return ""  # item gone; empty swap, polling stops naturally
    with NOTES_LOCK:
        pending, failed = uid in NOTES_PENDING, uid in NOTES_FAILED
    return note_block(date, uid, row["note"], pending, failed)
```

registered as `GET_ROUTES["/note-status"] = get_note_status`.

`post_note` returns the pending fragment directly on `HX-Request` (no DB
read needed — right after enqueueing, state is deterministically
"pending, no note yet"): `self.respond(note_block(date, uid, None, True,
False))`; else keeps the existing redirect.

Polling stops itself: because the swap is `outerHTML`, a response with
`pending=False` replaces the polling element with one that has no
`hx-trigger` attribute at all — no client-side script needed.

### 4.5 Build banner → scoped poll

Factor `manifest + banner` into `_build_section(date, rows, prow, building,
error) -> str`, wrapped in one `<div id="build-status">` (a static id is
fine — only one such element per page, no uid-escaping concern). The
`<form class="buildform">` inside gains a hidden `<input name="date">`
(missing today) plus `hx-post="/build" hx-target="#build-status"
hx-swap="outerHTML"`; the same div self-polls every 3s while
`BUILD["running"]`.

New route `GET_ROUTES["/build-status"]`, also imported directly into
`server.py` so `post_build` can call it on `HX-Request` the same way
`post_toggle` does:

```python
def post_build(self, form):
    with BUILD_LOCK:
        if not BUILD["running"]:
            BUILD["running"] = True
            BUILD["error"] = ""
            threading.Thread(target=build_worker, args=("notes" in form,),
                             daemon=True).start()
    date = form.get("date", [""])[0]
    if self.headers.get("HX-Request") == "true":
        self.respond(get_build_status({"date": [date]}))
    else:
        self.redirect("/")
```

**Known gap, flagged not silently absorbed:** once notes/build poll only
their own scoped element, nothing refreshes the item list itself when a
build finishes and adds new rows (today's meta-refresh reloaded
everything incidentally). Leave this as a manual refresh for v1 — do not
add `HX-Refresh` header plumbing preemptively; revisit only if it proves
to be an actual annoyance in practice.

### 4.6 Retire the meta-refresh mechanism

Once 4.4 and 4.5 both land: drop `page()`'s `refresh` parameter and the
`<meta http-equiv="refresh">` line in `layout.py` (confirmed via grep —
`page_queue` is the only caller of `refresh=`); drop
`refresh=building or bool(pending)` from `page_queue`'s final `page(...)`
call.

## 5. Files touched

| File | Change |
| --- | --- |
| `server/webapp/static/htmx.min.js` | new — vendored, pinned release |
| `server/webapp/assets.py` | add `HTMX_JS` bytes load next to `FAVICON` |
| `server/webapp/server.py` | serve `/static/htmx.min.js`; `HX-Request` branch in `post_toggle`/`post_note`/`post_build` |
| `server/webapp/pages/queue.py` | `render_item`, `note_block`, `_build_section`, `get_note_status`, `get_build_status`; `page_queue` shrinks to call them |
| `server/webapp/pages/__init__.py` | register `/note-status`, `/build-status` in `GET_ROUTES`; export new helpers |
| `server/webapp/layout.py` | drop meta-refresh, add htmx `<script>` tag |

No CSS changes needed — new wrapper divs (`#build-status`, `.notewrap`)
don't participate in any existing selector.

## 6. Verification

1. `python -m webapp` from `server/`; load `http://127.0.0.1:8765/`.
2. Toggle a queue item: network tab shows a fetch to `/toggle`, not a
   document navigation; the card's done/not-done state updates in place.
3. Click "Draft connection note": button is replaced by "drafting
   note…", which updates to the finished note (or failed state) within a
   few seconds, no page reload.
4. Click "Build today's queue" / "Fetch more targets": banner updates in
   place while running; button re-enables on completion, no full reload.
5. With JS disabled (or via `curl -X POST .../toggle`): confirm the plain
   `<form>` fallback still works (redirect-based, as before).
6. Confirm `/board`, `/due`, `/log`, `/company`, `/stats`, `/profile` are
   visually unchanged (only the new `<script>` tag is present).

## 7. Implementation order

1. Vendor htmx + static route + `<script>` tag — verify it loads.
2. Extract `render_item`/`note_block`/`_build_section` with no `hx-*`
   attributes yet — verify byte-identical output to today.
3. Wire up toggle (smallest, most isolated behavioral change).
4. Wire up note polling.
5. Wire up build polling, then remove the old meta-refresh mechanism last.
