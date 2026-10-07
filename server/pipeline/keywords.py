"""Skill/keyword normalization shared by the skill-gaps page and keyword
coverage: lower-case, trim, collapse whitespace, then map through
`[keywords].aliases` (variant → canonical, e.g. k8s → kubernetes).
"""
from __future__ import annotations

import re


def _clean(term: str) -> str:
    return re.sub(r"\s+", " ", str(term)).strip().lower()


def alias_map(cfg: dict) -> dict[str, str]:
    """`[keywords].aliases`, both sides cleaned."""
    raw = cfg.get("keywords", {}).get("aliases", {})
    return {_clean(k): _clean(v) for k, v in raw.items() if _clean(k)}


def normalize(term: str, aliases: dict[str, str]) -> str:
    """Canonical form of a skill name ("" for a blank one)."""
    key = _clean(term)
    return aliases.get(key, key)
