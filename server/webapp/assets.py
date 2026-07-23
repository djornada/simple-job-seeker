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
nav.tabs { display: flex; gap: 18px; font-size: 14px; }
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
article.target.done { opacity: .55; }
article.target.done h2 { text-decoration: line-through; }
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
p.linkrow { margin: 0; font-size: 13px; display: flex; gap: 14px; flex-wrap: wrap; }
p.note { margin: 8px 0 0; font-size: 13.5px; background: var(--paper);
  border-radius: 6px; padding: 8px 10px; }
p.note .len { font-family: var(--mono); font-size: 11px; color: var(--muted);
  margin-left: 6px; }
p.note.pending { color: var(--muted); font-style: italic; }
p.note.failed { color: var(--amber); background: var(--amber-bg); font-size: 12.5px; }
p.fit { margin: 6px 0 0; font-size: 13px; color: var(--accent-ink);
  border-left: 3px solid var(--accent); padding: 2px 0 2px 10px; }
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
section.stage h2 { font-family: var(--mono); font-size: 12px;
  letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
  border-bottom: 1px solid var(--line); padding-bottom: 6px; margin: 0 0 4px; }
.rowline { display: flex; gap: 14px; padding: 7px 2px; align-items: baseline;
  border-bottom: 1px solid var(--line); font-size: 14px; }
.rowline .when { font-family: var(--mono); font-size: 12px; color: var(--muted);
  min-width: 88px; }
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
.empty { margin: 40px 0; color: var(--muted); }
.hint { margin-top: 24px; color: var(--muted); font-size: 13px; }
@media (max-width: 620px) {
  form.logform { grid-template-columns: 1fr; }
  .manifest { flex-direction: column; align-items: flex-start; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

TABS = [("/", "Queue"), ("/board", "Board"), ("/due", "Due"), ("/log", "Log"),
        ("/stats", "Stats"), ("/profile", "Résumé")]

# favicon lives at the project root; loaded once, served as static bytes
try:
    FAVICON = (BASE_DIR / "favicon.ico").read_bytes()
except OSError:
    FAVICON = b""

# vendored (not CDN-loaded) so the webapp never makes an outbound request
HTMX_JS = (BASE_DIR / "webapp" / "static" / "htmx.min.js").read_bytes()
