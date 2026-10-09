"""Static assets: the stylesheet, the tab bar, and the favicon bytes."""
from __future__ import annotations

from utils import BASE_DIR

CSS = """
:root {
  --paper: #EDF1EE; --card: #FFFFFF; --ink: #17251F; --muted: #5A6962;
  --line: #D6DED8; --accent: #0E6B5C; --accent-ink: #0A5246;
  --amber: #9A5B12; --amber-bg: #F5E8D4;
  --mono: ui-monospace, "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--accent-ink); text-underline-offset: 2px; }
a:hover { color: var(--accent); }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 880px; margin: 0 auto; padding: 0 20px 64px; }
header.top { display: flex; align-items: baseline; gap: 24px;
  padding: 18px 0 14px; border-bottom: 1px solid var(--line); }
.wordmark { font-family: var(--mono); font-weight: 700; letter-spacing: -0.5px; }
.wordmark a { color: var(--ink); text-decoration: none; }
nav.tabs { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: 14px; }
nav.tabs a { text-decoration: none; color: var(--muted); padding: 2px 0; }
nav.tabs a:hover { color: var(--ink); }
nav.tabs a.active { color: var(--ink); box-shadow: 0 2px 0 var(--accent); }
.badge { font-family: var(--mono); font-size: 11px; background: var(--amber-bg);
  color: var(--amber); border-radius: 8px; padding: 0 6px; margin-left: 4px; }
.manifest { display: flex; justify-content: space-between; align-items: flex-end;
  gap: 24px; margin: 28px 0 8px; flex-wrap: wrap; }
.eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: .14em;
  color: var(--muted); text-transform: uppercase; }
.manifest h1 { font-size: 32px; letter-spacing: -0.02em; margin: 2px 0 0;
  font-weight: 750; font-family: var(--mono); }
.progress { display: flex; align-items: center; gap: 10px; padding-bottom: 8px; }
.segs { display: flex; gap: 3px; flex-wrap: wrap; max-width: 280px; }
.seg { width: 14px; height: 14px; border-radius: 3px;
  border: 1px solid var(--line); background: var(--card); }
.seg.on { background: var(--accent); border-color: var(--accent); }
.progress .count { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.buildform { display: flex; align-items: center; gap: 12px; padding-bottom: 6px; }
button.primary { background: var(--accent); color: #fff; border: 0;
  border-radius: 6px; padding: 8px 14px; font: 600 14px system-ui; cursor: pointer; }
button.primary:hover { background: var(--accent-ink); }
button.primary[disabled] { opacity: .5; cursor: default; }
label.opt { font-size: 13px; color: var(--muted); display: flex; gap: 5px;
  align-items: center; }
.banner { margin: 16px 0; padding: 10px 14px; border: 1px solid var(--line);
  border-left: 3px solid var(--accent); background: var(--card);
  border-radius: 6px; font-size: 14px; }
.banner.err { border-left-color: #8C2F1B; }
nav.dates { font-family: var(--mono); font-size: 12px; display: flex; gap: 12px;
  margin: 10px 0 18px; flex-wrap: wrap; }
nav.dates a { color: var(--muted); }
nav.dates a.cur { color: var(--ink); font-weight: 700; text-decoration: none; }
article.target { display: flex; gap: 14px; background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px;
  margin-bottom: 10px; }
/* a worked card collapses to one line: tick, company, title; unticking
   brings the rest back */
article.target.done { opacity: .55; padding: 8px 16px; align-items: center; }
article.target.done h2 { text-decoration: line-through; flex-shrink: 0; }
article.target.done > div { display: flex; gap: 10px; align-items: baseline;
  min-width: 0; }
article.target.done > div > :not(h2, p.meta) { display: none; }
article.target.done p.meta { margin: 0; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; }
.tick { width: 26px; height: 26px; border-radius: 6px;
  border: 1.5px solid var(--line); background: var(--paper); cursor: pointer;
  color: var(--accent); font-size: 15px; line-height: 1; }
.tick:hover { border-color: var(--accent); }
article.target h2 { font-size: 16px; margin: 0; display: flex; gap: 8px;
  align-items: baseline; }
.score { font-family: var(--mono); font-size: 11px; font-weight: 400;
  color: var(--muted); border: 1px solid var(--line); padding: 0 5px;
  border-radius: 8px; }
p.meta { margin: 2px 0 6px; color: var(--muted); font-size: 13px; }
/* a div: its inline forms (Log, I applied) would close a <p> */
.linkrow { margin: 0; font-size: 13px; display: flex; gap: 14px; flex-wrap: wrap; }
p.note { margin: 8px 0 0; font-size: 13.5px; background: var(--paper);
  border-radius: 6px; padding: 8px 10px; }
p.note .len { font-family: var(--mono); font-size: 11px; color: var(--muted);
  margin-left: 6px; }
p.note.pending { color: var(--muted); font-style: italic; }
p.note.failed { color: var(--amber); background: var(--amber-bg); font-size: 12.5px; }
p.fit { margin: 6px 0 0; font-size: 13px; color: var(--accent-ink);
  border-left: 3px solid var(--accent); padding: 2px 0 2px 10px; }
p.flags { margin: 6px 0 0; display: flex; flex-wrap: wrap; gap: 6px; }
.flag { font-size: 12px; background: var(--amber-bg); color: var(--amber);
  border-radius: 8px; padding: 1px 8px; }
.verdict { font-family: var(--mono); font-size: 11px; border-radius: 8px;
  padding: 0 6px; margin-right: 8px; background: var(--paper);
  color: var(--muted); border: 1px solid var(--line); }
.v-strong, .v-good { background: var(--accent); color: #fff;
  border-color: var(--accent); }
.v-moderate { color: var(--accent-ink); }
.v-weak, .v-poor { background: var(--amber-bg); color: var(--amber);
  border-color: var(--amber-bg); }
details.fitmore { margin: 4px 0 0; font-size: 12.5px; color: var(--ink); }
details.fitmore summary { cursor: pointer; color: var(--muted); }
details.fitmore ul { margin: 2px 0 6px; padding-left: 18px; }
p.dims { margin: 4px 0 0; font-family: var(--mono); font-size: 11.5px;
  color: var(--muted); }
table.kwtab { border-collapse: collapse; margin: 4px 0 2px;
  font-size: 12.5px; }
table.kwtab td { padding: 3px 14px 3px 0;
  border-bottom: 1px solid var(--line); }
table.kwtab td.kind { font-family: var(--mono); font-size: 11px;
  color: var(--muted); }
.kw { font-family: var(--mono); font-size: 11px; border-radius: 8px;
  padding: 0 6px; border: 1px solid var(--line); color: var(--accent-ink); }
.kw-covered { background: var(--accent); color: #fff;
  border-color: var(--accent); }
.kw-missing { background: var(--amber-bg); color: var(--amber);
  border-color: var(--amber-bg); }
p.fit .llm { font-family: var(--mono); font-size: 11px; color: var(--muted);
  margin-right: 6px; }
table.stats { width: 100%; border-collapse: collapse; font-size: 14px;
  margin: 4px 0 8px; }
table.stats th, table.stats td { text-align: right; padding: 6px 10px;
  border-bottom: 1px solid var(--line); }
table.stats th:first-child, table.stats td:first-child { text-align: left; }
table.stats th { font-family: var(--mono); font-size: 11px; letter-spacing: .06em;
  text-transform: uppercase; color: var(--muted); font-weight: 600; }
table.stats td.rate { font-family: var(--mono); }
.caveat { color: var(--muted); font-size: 12.5px; margin: 2px 0 18px; }
.scrollx { overflow-x: auto; }  /* a table wider than a phone scrolls alone */
pre.profiletext { white-space: pre-wrap; word-break: break-word;
  background: var(--card); border: 1px solid var(--line); border-radius: 8px;
  padding: 12px 14px; font: 12.5px/1.55 var(--mono); color: var(--ink);
  margin: 4px 0 18px; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 18px; }
input[type=file] { padding: 6px; background: var(--card); cursor: pointer; }
button.ghost { background: none; border: 1px solid var(--line);
  border-radius: 6px; padding: 4px 10px; font-size: 12.5px;
  color: var(--accent-ink); cursor: pointer; }
button.ghost:hover { border-color: var(--accent); }
section.stage { margin: 26px 0; }
section.stage h2, details.recent > summary { font-family: var(--mono);
  font-size: 12px;
  letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding-bottom: 6px; margin: 0 0 4px; }
.rowline { display: flex; gap: 14px; padding: 7px 2px; align-items: baseline;
  border-bottom: 1px solid var(--line); font-size: 14px; }
.rowline .when, details.co > summary .when { font-family: var(--mono);
  font-size: 12px; color: var(--muted); min-width: 88px; }
/* Board: one row per company, expanding to its timeline */
details.co { border-bottom: 1px solid var(--line); }
details.co > summary { display: flex; gap: 14px; padding: 7px 2px;
  align-items: baseline; font-size: 14px; cursor: pointer; list-style: none; }
details.co > summary::-webkit-details-marker { display: none; }
details.co > summary::before { content: "▸"; color: var(--muted); width: 8px; }
details.co[open] > summary::before { content: "▾"; }
details.co > summary .name { flex: 1; }
details.co > summary:hover .name { color: var(--accent-ink); }
details.co .tl { margin: 0 0 12px 22px; }
details.co .tl p.meta { margin: 0 0 2px; }
details.co .tl .rowline { font-size: 13.5px; }
.tlactions { margin: 6px 0 0; }
details.recent { margin: 26px 0; }
/* Board: what needs you, above the stages */
section.due { margin: 22px 0; padding: 12px 16px 10px; background: var(--card);
  border: 1px solid var(--line); border-left: 3px solid var(--amber);
  border-radius: 8px; }
section.due h2 { font-family: var(--mono); font-size: 12px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--amber); margin: 0; }
section.due h3 { font-size: 12.5px; font-weight: 600; color: var(--muted);
  margin: 12px 0 0; }
section.due .rowline:last-child { border-bottom: 0; }
details.recent > summary { cursor: pointer; }
dialog.logdlg { border: 0; padding: 0; background: none;
  width: min(560px, calc(100vw - 32px)); }
dialog.logdlg::backdrop { background: rgb(23 37 31 / .4); }
dialog.logdlg form.logform { margin: 0; box-shadow: 0 12px 32px rgb(0 0 0 / .18); }
dialog.logdlg h2 { font-size: 16px; margin: 0; }
.dlgbtns { display: flex; gap: 10px; align-items: center; }
.tag-overdue { font-family: var(--mono); font-size: 11px; color: var(--amber);
  background: var(--amber-bg); padding: 0 6px; border-radius: 8px; }
form.logform { background: var(--card); border: 1px solid var(--line);
  border-radius: 8px; padding: 16px; display: grid;
  grid-template-columns: 1fr 1fr; gap: 12px; margin: 8px 0 20px; }
form.logform label { font-size: 12.5px; color: var(--muted); display: flex;
  flex-direction: column; gap: 4px; }
input, select { font: 14px system-ui; padding: 7px 9px;
  border: 1px solid var(--line); border-radius: 6px; background: var(--paper);
  color: var(--ink); }
.full { grid-column: 1 / -1; }
.rowline.app { flex-wrap: wrap; }
.appactions { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.appactions form { display: flex; gap: 6px; align-items: center; margin: 0; }
.appactions select, .appactions input { padding: 3px 6px; font-size: 12.5px; }
.status { font-family: var(--mono); font-size: 11px; color: var(--accent-ink);
  border: 1px solid var(--line); border-radius: 8px; padding: 0 6px; }
.apperr { color: #8C2F1B; font-size: 12.5px; }
.expired { font-family: var(--mono); font-size: 11px; color: #8C2F1B;
  background: #F6E1DC; border-radius: 8px; padding: 0 6px; }
.sweep { display: flex; gap: 12px; align-items: center; margin: 10px 0 0;
  font-size: 13.5px; }
form.inline { display: inline; margin: 0; }
button.linkbtn { background: none; border: 0; padding: 0; font: inherit;
  color: var(--accent-ink); text-decoration: underline;
  text-underline-offset: 2px; cursor: pointer; }
.empty { margin: 40px 0; color: var(--muted); }
#items > p.empty:not(:only-child) { display: none; }  /* a build streamed a card in */
.posting { margin: 18px 0 0; line-height: 1.6; overflow-wrap: anywhere; }
.hint { margin-top: 24px; color: var(--muted); font-size: 13px; }
@media (max-width: 620px) {
  form.logform { grid-template-columns: 1fr; }
  .manifest { flex-direction: column; align-items: flex-start; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

TABS = [("/", "Queue"), ("/board", "Board"), ("/applications", "Applications"),
        ("/stats", "Stats"), ("/profile", "Résumé")]

# favicon lives at the project root; loaded once, served as static bytes
try:
    FAVICON = (BASE_DIR / "favicon.ico").read_bytes()
except OSError:
    FAVICON = b""

# vendored (not CDN-loaded) so the webapp never makes an outbound request
HTMX_JS = (BASE_DIR / "webapp" / "static" / "htmx.min.js").read_bytes()
