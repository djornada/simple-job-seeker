"""Weighted fit framework: parse the LLM's per-dimension reply, weigh it.

The model scores four dimensions 0-100 (skills, experience, culture,
career) and lists strengths, gaps and missing skills; Python computes the
overall score, never the model: a weighted average with `[resume.weights]`.
`llm_score = overall / 10` keeps every 0-10 consumer (`min_llm_score`, the
/stats bands, the markdown render, the extension popup) working unchanged.

Parsing is defensive: a missing or non-numeric dimension is dropped and
the remaining weights renormalized; with no valid dimension, a legacy
0-10 `score` key is used if present, else the job is unscored (`{}`).
"""
from __future__ import annotations

import json
import re

DIMENSIONS = ("skills", "experience", "culture", "career")
DEFAULT_WEIGHTS = {"skills": 30, "experience": 25, "culture": 15, "career": 30}
VERDICTS = ((75, "strong"), (60, "good"), (45, "moderate"), (30, "weak"),
            (0, "poor"))


def verdict(overall: float) -> str:
    return next(label for floor, label in VERDICTS if overall >= floor)


def parse_json_object(text: str) -> dict | None:
    """The first JSON object in a reply, tolerating code fences or prose
    around it. None when there isn't one."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for candidate in (text, text[text.find("{"):text.rfind("}") + 1]):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _number(value: object, top: float) -> float | None:
    """A float clamped to 0..top, or None for anything non-numeric."""
    if isinstance(value, bool):
        return None
    try:
        n = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if n != n else min(max(n, 0.0), top)  # n != n: NaN


def _lines(value: object, limit: int, width: int) -> list[str]:
    items = value if isinstance(value, list) else [value] if value else []
    out = [str(v).strip()[:width] for v in items if str(v).strip()]
    return out[:limit]


def _weights(cfg: dict) -> dict[str, float]:
    raw = {**DEFAULT_WEIGHTS, **cfg.get("resume", {}).get("weights", {})}
    return {d: w for d in DIMENSIONS
            if (w := _number(raw.get(d), float("inf"))) is not None}


def score_reply(data: dict, cfg: dict) -> dict:
    """Turn a parsed reply into {"score": 0-10, "fit": str, "detail": {...}}
    (`detail` is what `queue_items.fit_json` stores), or {} if unscorable."""
    fit = str(data.get("fit", "")).strip()
    dims = {d: v for d in DIMENSIONS
            if (v := _number(data.get(d), 100.0)) is not None}
    weights = _weights(cfg)
    total = sum(weights.get(d, 0.0) for d in dims)
    if dims and total > 0:
        overall = sum(v * weights.get(d, 0.0) for d, v in dims.items()) / total
    else:
        legacy = _number(data.get("score"), 10.0)
        if legacy is None:
            return {}
        overall, dims = legacy * 10, {}
    overall = round(overall, 1)
    detail = {
        "dimensions": dims,
        "overall": overall,
        "verdict": verdict(overall),
        "strengths": _lines(data.get("strengths"), 3, 160),
        "gaps": _lines(data.get("gaps"), 3, 160),
        "missing_skills": _lines(data.get("missing_skills"), 5, 40),
    }
    return {"score": overall / 10, "fit": fit, "detail": detail}
