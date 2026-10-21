"""Pluggable LLM backend, one module per provider (mirrors sources/).

`[llm].provider` selects the backend: "ollama" (default, local) or "openai"
for any OpenAI-compatible chat endpoint (e.g. NVIDIA NIM). Both backends
return None when unreachable so callers get a uniform fallback; `complete`
raises instead, for callers that need the reason (the web UI's /llm test).
"""
from __future__ import annotations

import re
from types import ModuleType

from . import ollama, openai
from .base import LLMError

__all__ = ["LLMError", "complete", "generate", "settings", "strip_think"]


def strip_think(text: str) -> str:
    """qwen3 leaks <think>…</think> even with think disabled; drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _backend(cfg: dict) -> ModuleType:
    provider = cfg.get("llm", {}).get("provider", "ollama").lower()
    return openai if provider in ("openai", "nvidia", "nim") else ollama


def generate(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str | None:
    """One completion from the configured provider; None if unreachable."""
    return _backend(cfg).generate(cfg, prompt, fmt=fmt, options=options,
                                  timeout=timeout)


def complete(cfg: dict, prompt: str, *, fmt: str | None = None,
             options: dict | None = None, timeout: int = 300) -> str:
    """`generate`, but raising LLMError (HTTP error) or OSError
    (unreachable, timeout) instead of returning None."""
    return _backend(cfg).complete(cfg, prompt, fmt=fmt, options=options,
                                  timeout=timeout)


def settings(cfg: dict) -> dict[str, str]:
    """The configured provider, the backend it resolves to, and what that
    backend will call — for display; never includes an API key."""
    backend = _backend(cfg)
    return {"provider": cfg.get("llm", {}).get("provider", "ollama"),
            "backend": backend.__name__.rsplit(".", 1)[-1],
            **backend.settings(cfg)}
