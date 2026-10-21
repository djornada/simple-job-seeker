"""Local Ollama backend: one /api/generate call."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import LLMError

DEFAULT_MODEL = "qwen3:4b"
DEFAULT_URL = "http://localhost:11434"


def settings(cfg: dict) -> dict[str, str]:
    """What `complete` will call, for display."""
    o = cfg.get("ollama", {})
    return {"model": o.get("model", DEFAULT_MODEL),
            "endpoint": o.get("url", DEFAULT_URL)}


def complete(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str:
    """Like `generate`, but raises instead of returning None: LLMError on an
    HTTP error (404 = model not pulled), OSError when the server is down."""
    o = cfg.get("ollama", {})
    payload: dict = {
        "model": o.get("model", DEFAULT_MODEL),
        "prompt": prompt,
        "stream": False,
        "think": False,
    }
    if fmt:
        payload["format"] = fmt
    if options:
        payload["options"] = options
    url = o.get("url", DEFAULT_URL)
    req = urllib.request.Request(
        url + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("response", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200].strip()
        raise LLMError(f"{url} HTTP {e.code}: {body}") from e


def generate(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str | None:
    """Returns raw response text, or None if the server is unreachable."""
    try:
        return complete(cfg, prompt, fmt=fmt, options=options, timeout=timeout)
    except (LLMError, OSError):
        return None
