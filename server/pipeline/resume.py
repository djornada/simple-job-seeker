"""Resume-in-the-loop: read the imported profile, LLM-judge fit, draft notes.

Reads the profile stored by `python -m profile import`; with no profile or
the LLM backend down, `rerank_with_resume` is a no-op and `draft_note`
returns None, so the pipeline degrades to keyword-only cleanly.
"""
from __future__ import annotations

import json
import sqlite3

import llm
from db import db_connect
from sources import Job


def load_profile_text(conn: sqlite3.Connection) -> str | None:
    """Compact resume text for the LLM re-rank, or None if never imported."""
    try:
        row = conn.execute("SELECT text FROM profile WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def load_profile_bits(conn: sqlite3.Connection) -> tuple[str, list[str]] | None:
    """Headline + skills for note personalization, or None if never imported."""
    try:
        row = conn.execute(
            "SELECT headline, skills_json FROM profile WHERE id = 1").fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return (row[0] or ""), (json.loads(row[1]) if row[1] else [])


def draft_note(job: Job, cfg: dict) -> str | None:
    conn = db_connect()
    bits = load_profile_bits(conn)
    profile_text = load_profile_text(conn)
    conn.close()
    if bits and bits[0]:
        headline, skills = bits
        sender = f"a {headline}"
        if skills:
            sender += f" (core skills: {', '.join(skills[:6])})"
    else:
        sender = ("a senior software engineer / tech lead "
                  "(React, TypeScript, Node.js)")
    # full imported experience gives the model something concrete to reference
    background = f"\n\nSENDER BACKGROUND:\n{profile_text}" if profile_text else ""
    prompt = (
        "Write a LinkedIn connection note under 200 characters, in English. "
        f"From: {sender} reaching out about a role. Friendly, direct, no "
        "agency-speak, no emojis, no 'I hope this finds you well'. Mention the "
        "company naturally, and draw on the sender's background where it's "
        "relevant to the role (still under 200 characters).\n\n"
        f"Company: {job.company}\nRole: {job.title}{background}\n\n"
        "Reply with the note text only."
    )
    raw = llm.generate(cfg, prompt, options={"temperature": 0.7})
    if raw is None:
        return None
    note = llm.strip_think(raw).strip().strip('"')
    return note[:200] if note else None


def judge_fit(job: Job, profile_text: str, cfg: dict) -> dict | None:
    """Score one job against the profile. None = LLM backend unreachable."""
    prompt = (
        "Rate how well a remote job fits a candidate, 0-10, based only on the "
        "profile and the posting. Reply as JSON only: "
        '{"score": <integer 0-10>, "fit": "<one line: why it fits / what to '
        'emphasize>"}.\n\n'
        f"CANDIDATE PROFILE:\n{profile_text}\n\n"
        f"JOB\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Description: {job.description}\n"
    )
    raw = llm.generate(cfg, prompt, fmt="json")
    if raw is None:
        return None
    try:
        data = json.loads(llm.strip_think(raw))
    except (json.JSONDecodeError, TypeError):
        return {}
    try:
        score = float(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0.0
    return {"score": score, "fit": str(data.get("fit", "")).strip()}


def rerank_with_resume(jobs: list[Job], profile_text: str, cfg: dict) -> list[Job]:
    """Re-rank keyword-gated jobs by LLM-judged fit with the resume.

    LLM score is primary, keyword score the tiebreak. Jobs below
    `[resume].min_llm_score` are dropped. If the LLM backend is unreachable
    the stage is a no-op and the keyword order is returned untouched.
    """
    r = cfg.get("resume", {})
    shortlist = r.get("shortlist", 30)
    floor = r.get("min_llm_score", 5)

    ranked = sorted(jobs, key=lambda j: j.score, reverse=True)
    head, tail = ranked[:shortlist], ranked[shortlist:]

    scored: list[Job] = []
    for job in head:
        result = judge_fit(job, profile_text, cfg)
        if result is None:  # backend died mid-run: keep the keyword order
            return jobs
        job.llm_score = result.get("score", 0.0)
        job.fit_note = result.get("fit", "")
        scored.append(job)

    if floor:
        scored = [j for j in scored if (j.llm_score or 0) >= floor]
    scored.sort(key=lambda j: (j.llm_score or 0, j.score), reverse=True)
    return scored + tail
