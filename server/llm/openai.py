"""OpenAI-compatible backend (e.g. NVIDIA NIM): one /chat/completions call.

The API key is read from the env var named in `[openai].api_key_env` so no
secret is committed. HTTP errors (401 bad key, 429 rate limit, 5xx) are
logged to stderr and collapse to None, matching the Ollama backend so the
fallback is uniform.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from .base import LLMError

DEFAULT_MODEL = "z-ai/glm-5.2"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


def settings(cfg: dict) -> dict[str, str]:
    """What `complete` will call, for display: the key's env var name and
    whether it's set, never the key itself."""
    o = cfg.get("openai", {})
    env = o.get("api_key_env", "OPENAI_API_KEY")
    return {
        "model": o.get("model", DEFAULT_MODEL),
        "endpoint": o.get("base_url", DEFAULT_BASE_URL),
        "api key": f"${env} " + ("set" if os.environ.get(env) else "not set"),
    }


def complete(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str:
    """Like `generate`, but raises instead of returning None: LLMError on an
    HTTP error, OSError when the endpoint is unreachable or times out."""
    o = cfg.get("openai", {})
    api_key = os.environ.get(o.get("api_key_env", "OPENAI_API_KEY"), "")
    payload: dict = {
        "model": o.get("model", DEFAULT_MODEL),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if options and "temperature" in options:
        payload["temperature"] = options["temperature"]
    if fmt == "json":  # OpenAI/NIM ask for JSON via response_format
        payload["response_format"] = {"type": "json_object"}
    base = o.get("base_url", DEFAULT_BASE_URL).rstrip("/")
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:  # 401 bad key, 429 rate limit, 5xx…
        body = e.read().decode("utf-8", "replace")[:200].strip()
        raise LLMError(f"{base} HTTP {e.code}: {body}") from e
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def generate(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str | None:
    try:
        return complete(cfg, prompt, fmt=fmt, options=options, timeout=timeout)
    except LLMError as e:
        print(f"[llm] {e}", file=sys.stderr)
        return None
    except OSError:
        return None
