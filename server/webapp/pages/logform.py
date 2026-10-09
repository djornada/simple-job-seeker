"""`/log-form` — the log-touchpoint dialog, shared by Board and Queue.

A page carries one `log_dialog`; each `log_button` opens it. With htmx the
button GETs `/log-form` into the dialog and a small script shows it as a
modal. Without JS the same button is a plain GET to `/board?log=<company>`,
which renders the dialog already open. Either way the form posts to
`POST /add`, which lands on the company's Board row.

Ticking a queue card fills the dialog too (`queue.log_prompt`, an htmx
out-of-band swap). That form posts with htmx and swaps the card back in,
so saving stays on the queue.
"""
from __future__ import annotations

import tracker

from ..state import db, esc

# Show the dialog once htmx has loaded a form into it: a Log button's
# swap, or a ticked card's out-of-band prompt. Close it once a prompt's
# form has saved. A dialog the server rendered open (`/board?log=`) is
# reopened as a modal, so Esc and the backdrop work the same as after a
# button click.
_SCRIPT = """<script>
{ const show = e => {
    const d = e.detail.target;
    if (d.id === "logdlg" && !d.open) d.showModal();
  };
  document.addEventListener("htmx:afterSwap", show);
  document.addEventListener("htmx:oobAfterSwap", show);
  document.addEventListener("htmx:afterRequest", e => {
    const d = e.detail.elt.closest("#logdlg");
    if (d && e.detail.successful) d.close();
  });
  const d = document.getElementById("logdlg");
  if (d.open) { d.close(); d.showModal(); } }
</script>"""


def log_form(company: str = "", action: str = "visited", target: str = "",
             hidden: dict[str, str] | None = None) -> str:
    """The form: company (autocompletes from queued and contacted
    companies), person, action, follow-up days, note. Cancel closes the
    dialog without JS (`formmethod="dialog"`).

    With `target` (a CSS selector) the form posts with htmx and its
    response replaces that element; `hidden` rides along. Cancel is then a
    plain button: htmx would post a `formmethod="dialog"` submit too."""
    conn = db()
    companies = [r[0] for r in conn.execute(
        "SELECT DISTINCT company FROM outreach "
        "UNION SELECT company FROM queued_companies ORDER BY 1")]
    conn.close()
    options = "".join(f'<option value="{esc(c)}">' for c in companies)
    action_opts = "".join(
        f'<option value="{a}"{" selected" if a == action else ""}>{a}</option>'
        for a in tracker.ACTIONS)
    # focus the first empty field: person when the company is prefilled
    on_company, on_person = ("", " autofocus") if company else (" autofocus", "")
    hx, cancel = "", '<button class="ghost" formmethod="dialog" formnovalidate>Cancel</button>'
    if target:
        hx = f' hx-post="/add" hx-target="{esc(target)}" hx-swap="outerHTML"'
        cancel = ('<button type="button" class="ghost" '
                  'onclick="this.closest(\'dialog\').close()">Cancel</button>')
    extra = "".join(f'<input type="hidden" name="{esc(k)}" value="{esc(v)}">'
                    for k, v in (hidden or {}).items())
    return f"""
<form class="logform" method="post" action="/add"{hx}>{extra}
  <h2 class="full">Log a touchpoint</h2>
  <label>Company
    <input name="company" list="companies" required{on_company}
           value="{esc(company)}">
    <datalist id="companies">{options}</datalist>
  </label>
  <label>Person
    <input name="person" placeholder="who you talked to"{on_person}>
  </label>
  <label>Action <select name="action">{action_opts}</select></label>
  <label>Follow-up in (days)
    <input name="followup" type="number" min="0" max="365" placeholder="none">
  </label>
  <label class="full">Note
    <input name="note" placeholder="context for future you">
  </label>
  <div class="full dlgbtns">
    <button class="primary">Log touchpoint</button>
    {cancel}
  </div>
</form>"""


def log_dialog(company: str | None = None) -> str:
    """The page's dialog: empty until a `log_button` loads the form, or
    rendered open with it for `company` (`/board?log=`, no JS needed)."""
    if company is None:
        return f'<dialog id="logdlg" class="logdlg"></dialog>{_SCRIPT}'
    return (f'<dialog id="logdlg" class="logdlg" open>{log_form(company)}'
            f'</dialog>{_SCRIPT}')


def log_button(company: str = "", label: str = "Log",
               cls: str = "ghost") -> str:
    """Opens the page's log dialog with `company` prefilled."""
    return (f'<form class="inline" method="get" action="/board" '
            f'hx-get="/log-form" hx-target="#logdlg">'
            f'<input type="hidden" name="log" value="{esc(company)}">'
            f'<button class="{cls}">{label}</button></form>')


def get_log_form(params: dict[str, list[str]]) -> str:
    """`/log-form?log=<company>`: the form, for htmx to load into the dialog."""
    return log_form(params.get("log", [""])[0].strip())
