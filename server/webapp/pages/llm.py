"""`/llm` — the LLM backend config.toml selects, and a test button that sends
it one tiny JSON-mode prompt (the mode the re-rank and keyword checks use)."""
from __future__ import annotations

import time

import llm
from pipeline.fit import parse_json_object
from utils import load_config

from ..layout import page
from ..state import esc

PROBE = 'Reply with only this JSON object and nothing else: {"ok": true}'
PROBE_TIMEOUT = 120  # a cold Ollama model can take a while to load


def llm_result(ok: bool, message: str, reply: str = "") -> str:
    cls = "banner" if ok else "banner err"
    pre = f'<pre class="profiletext">{esc(reply[:500])}</pre>' if reply else ""
    return (f'<div id="llm-result"><p class="{cls}">{esc(message)}</p>'
            f'{pre}</div>')


def llm_test() -> str:
    """Send PROBE to the configured backend; the result block says whether
    it answered, how fast, and whether the reply parsed as JSON."""
    cfg = load_config()
    started = time.monotonic()
    try:
        raw = llm.complete(cfg, PROBE, fmt="json",
                           options={"temperature": 0}, timeout=PROBE_TIMEOUT)
    except (llm.LLMError, OSError) as e:
        took = time.monotonic() - started
        return llm_result(False, f"Failed after {took:.1f}s: {e}")
    took = time.monotonic() - started
    reply = llm.strip_think(raw)
    if not reply:
        return llm_result(False, f"Answered in {took:.1f}s, but with an empty reply.")
    if parse_json_object(reply) is None:
        return llm_result(False, f"Answered in {took:.1f}s, but not with JSON — "
                                 "the re-rank and keyword checks need JSON.", reply)
    return llm_result(True, f"Working — answered with JSON in {took:.1f}s.", reply)


def page_llm(params: dict[str, list[str]], result: str = "") -> str:
    rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>"
                   for k, v in llm.settings(load_config()).items())
    body = f"""
<div class="manifest">
  <div>
    <div class="eyebrow">LLM · from config.toml</div>
    <h1>Model check</h1>
  </div>
</div>
<div class="scrollx"><table class="stats kv"><tbody>{rows}</tbody></table></div>
<form class="buildform" method="post" action="/llm/test" hx-post="/llm/test"
      hx-target="#llm-result" hx-swap="outerHTML" hx-disabled-elt="find button">
  <button class="primary">Test model</button>
  <span class="htmx-indicator caveat" style="margin:0">sending a test prompt…</span>
</form>
{result or '<div id="llm-result"></div>'}
<p class="hint">Sends one short prompt in JSON mode to the endpoint above
(it counts against a hosted provider's quota). config.toml is re-read on every
request, so edit it and test again — no restart needed. A key changed in .env
needs a restart, since a variable already loaded isn't overwritten.</p>"""
    return page("LLM", "/llm", body)
