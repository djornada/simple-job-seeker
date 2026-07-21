"""The pipeline stages between the job boards and the daily queue.

One concern per module (mirrors sources/ and db/):
- scoring.py — `score_job` keyword scoring (role keyword gates, stack adds)
- select.py  — `select_queue`: score → filter → per-company dedup → cap
- resume.py  — resume-in-the-loop over llm/: `rerank_with_resume`,
  `draft_note`, and the profile readers
- links.py   — `build_links`: LinkedIn people-search + Google x-ray URLs
- render.py  — `render` (queue → markdown) and `show_stats`, for the CLI

queue_agent is the entrypoint over this package and re-exports the facade
as `qa.*` for the web UI.
"""
from __future__ import annotations

from .links import build_links
from .render import render, show_stats
from .resume import (
    draft_note,
    load_profile_bits,
    load_profile_text,
    rerank_with_resume,
)
from .scoring import score_job
from .select import select_queue

__all__ = ["build_links", "draft_note", "load_profile_bits",
           "load_profile_text", "render", "rerank_with_resume", "score_job",
           "select_queue", "show_stats"]
