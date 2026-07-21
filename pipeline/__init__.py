"""The pipeline stages between the job boards and the daily queue.

One concern per module (mirrors sources/ and db/):
- scoring.py — `score_job` keyword scoring (role keyword gates, stack adds)
- select.py  — `select_queue`: score → filter → per-company dedup → cap
- resume.py  — resume-in-the-loop over llm/: `rerank_with_resume`,
  `draft_note`, and the profile readers
- build.py   — `build_queue`: the shared use case (collect → select →
  optional re-rank) consumed directly by both the CLI and the web UI
- links.py   — `build_links`: LinkedIn people-search + Google x-ray URLs
- render.py  — `render` (queue → markdown) and `show_stats`, for the CLI

Each adapter (queue_agent.py, webapp/) imports what it needs straight from
this package and from db/, sources/, utils/ — there is no facade to keep in
sync; every dependency points at the concrete module that owns it.
"""
from __future__ import annotations

from .build import build_queue
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

__all__ = ["build_links", "build_queue", "draft_note", "load_profile_bits",
           "load_profile_text", "render", "rerank_with_resume", "score_job",
           "select_queue", "show_stats"]
