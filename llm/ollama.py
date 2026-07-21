"""Local Ollama backend: one /api/generate call."""
from __future__ import annotations

import json
import urllib.request


def generate(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str | None:
    """Returns raw response text, or None if the server is unreachable."""
    o = cfg.get("ollama", {})
    payload: dict = {
        "model": o.get("model", "qwen3:4b"),
        "prompt": prompt,
        "stream": False,
        "think": False,
    }
    if fmt:
        payload["format"] = fmt
    if options:
        payload["options"] = options
    req = urllib.request.Request(
        o.get("url", "http://localhost:11434") + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("response", "")
    except OSError:
        return None
