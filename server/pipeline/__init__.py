"""The pipeline stages between the job boards and the daily queue.

One concern per module (mirrors sources/ and db/):
- fit.py     — weighted fit framework: `score_reply` weighs the LLM's
  four 0-100 dimensions with `[resume.weights]` into overall + verdict
- gates.py   — `check_gates`: language and eligibility gates (`[gates]`)
- scoring.py — `score_job` keyword scoring (gates first, role keyword
  required, stack adds)
- select.py  — `select_queue`: score → filter → per-company dedup → cap
- resume.py  — resume-in-the-loop over llm/: `rerank_with_resume`,
  `judge_fit` (the single-job primitive it batches over), `draft_note`,
  and the profile readers
- build.py   — `build_queue`: the shared use case (collect → select →
  optional re-rank) consumed directly by both the CLI and the web UI
- rate.py    — `rate_jobs`: scores ad-hoc jobs/posts from the browser
  extension the same way (score_job + judge_fit) and persists anything
  that clears the bar into today's queue
- expiry.py  — `recheck`: re-visit archived postings on their boards (never
  LinkedIn) and mark the ones taken down
- keywords.py — `normalize`/`alias_map`: skill names lower-cased, trimmed,
  mapped through `[keywords].aliases` (the gaps page and keyword coverage)
- links.py   — `build_links`: LinkedIn people-search + Google x-ray URLs
- render.py  — `render` (queue → markdown) and `show_stats`, for the CLI

Each adapter (queue_agent.py, webapp/) imports what it needs straight from
this package and from db/, sources/, utils/ — there is no facade to keep in
sync; every dependency points at the concrete module that owns it.
"""
from __future__ import annotations

from .build import build_queue
from .expiry import recheck
from .gates import check_gates
from .links import build_links
from .rate import rate_jobs
from .render import render, show_stats
from .resume import (
    draft_note,
    judge_fit,
    load_profile_bits,
    load_profile_text,
    rerank_with_resume,
)
from .scoring import score_job
from .select import select_queue

__all__ = ["build_links", "build_queue", "check_gates", "draft_note",
           "judge_fit", "load_profile_bits", "load_profile_text", "rate_jobs",
           "recheck", "render", "rerank_with_resume", "score_job",
           "select_queue", "show_stats"]
