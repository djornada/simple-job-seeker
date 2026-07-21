"""Pluggable LLM backend, one module per provider (mirrors sources/).

`[llm].provider` selects the backend: "ollama" (default, local) or "openai"
for any OpenAI-compatible chat endpoint (e.g. NVIDIA NIM). Both backends
return None when unreachable so callers get a uniform fallback.
"""
from __future__ import annotations

import re

from . import ollama, openai

__all__ = ["generate", "strip_think"]


def strip_think(text: str) -> str:
    """qwen3 leaks <think>…</think> even with think disabled; drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def generate(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str | None:
    """One completion from the configured provider; None if unreachable."""
    provider = cfg.get("llm", {}).get("provider", "ollama").lower()
    if provider in ("openai", "nvidia", "nim"):
        return openai.generate(cfg, prompt, fmt=fmt, options=options,
                               timeout=timeout)
    return ollama.generate(cfg, prompt, fmt=fmt, options=options,
                           timeout=timeout)
