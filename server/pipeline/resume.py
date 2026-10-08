"""Resume-in-the-loop: read the imported profile, LLM-judge fit, draft notes.

Reads the profile stored by `python -m profile import`; with no profile or
the LLM backend down, `rerank_with_resume` is a no-op and `draft_note`
returns None, so the pipeline degrades to keyword-only cleanly.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable

import llm
from db import db_connect
from sources import Job

from .fit import parse_json_object, score_reply


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


NOTE_LIMIT = 200  # LinkedIn's cap on a connection-request note

# A named opener the model adds despite the no-names rule ("Hi Sam,"):
# 1-3 capitalized words, then a comma or "!". "Hi there," is left alone.
_GREETING_RE = re.compile(
    r"^(?i:hi|hello|hey|dear)\s+(?:[A-Z][\w'.-]*\s?){1,3}([,!])\s*")
# A trailing signature: " — Sam", or after the last sentence "Best, Sam"
# or a bare "Sam". A spaced dash and a sentence end keep "Full-Stack
# Engineer" and "at Best Buy" intact; notes go out unsigned.
_SIGNOFF_RE = re.compile(
    r"(?:\s+[-–—]|(?<=[.!?])\s+(?:(?i:(?:best|kind|warm)\s+regards|best|"
    r"regards|cheers|thanks|thank you|sincerely)[,!]?)?)"
    r"\s*(?:[A-Z][\w'-]*\s?){1,3}$")
_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def _tidy_note(note: str) -> str:
    """Enforce in code what the prompt asks for: one line, no quotes, no
    named greeting or sign-off."""
    note = " ".join(note.split()).strip('"“”')
    note = _GREETING_RE.sub(r"Hi\1 ", note, count=1)
    return _SIGNOFF_RE.sub("", note).strip()


def _fit_note(note: str) -> str:
    """At most NOTE_LIMIT chars: cut at the last full sentence that fits,
    else the last whole word — never mid-word."""
    if len(note) <= NOTE_LIMIT:
        return note
    ends = [m.end() for m in _SENTENCE_END_RE.finditer(note)
            if m.end() <= NOTE_LIMIT]
    if ends:
        return note[:ends[-1]]
    head = note[:NOTE_LIMIT + 1]  # +1: a word ending right at the cap fits
    cut = head.rsplit(" ", 1)[0] if " " in head else note[:NOTE_LIMIT]
    return cut.rstrip(",;:-–— ")


def draft_note(job: Job, cfg: dict) -> str | None:
    conn = db_connect()
    bits = load_profile_bits(conn)
    profile_text = load_profile_text(conn)
    conn.close()
    if bits and bits[0]:
        headline, skills = bits
        me = f"a {headline}"
        if skills:
            me += f" (core skills: {', '.join(skills[:6])})"
    else:
        me = ("a senior software engineer / tech lead "
              "(React, TypeScript, Node.js)")
    roles = cfg.get("targets", {}).get(
        "people_roles", ["Technical Recruiter", "Engineering Manager"])
    # full imported experience gives the model something concrete to
    # reference; labelled as the candidate's so the model doesn't write
    # to its owner (drafts used to open "Hi <name>, I saw your profile")
    background = (f"\n\nMY BACKGROUND (I am the candidate):\n{profile_text}"
                  if profile_text else "")
    prompt = (
        "You are a job candidate writing a LinkedIn connection note. Write "
        f"in the first person, as me: {me}. The reader is the "
        f"{' or '.join(roles)} at {job.company}; you don't know their name.\n"
        "Rules:\n"
        # the model overshoots a stated cap by ~20%, and _fit_note cuts
        # at a sentence end, so ask for less and lead with what must survive
        f"- Under 160 characters (hard limit {NOTE_LIMIT}), in English, two "
        "short sentences.\n"
        "- First sentence: the role and the company I'm reaching out about. "
        "Second: one concrete result or project of mine that fits it. Don't "
        "introduce me by job title or list my skills.\n"
        "- No names at all: don't greet anyone by name and don't sign it. "
        'Open with "Hi," or no greeting.\n'
        "- I'm the one reaching out: never praise the reader's profile or "
        'experience, and never write as the company ("our team", "our '
        'needs").\n'
        "- Friendly and direct: no agency-speak, no emojis, no 'I hope this "
        "finds you well'.\n\n"
        f"Company: {job.company}\nRole: {job.title}{background}\n\n"
        "Reply with the note text only."
    )
    note = ""
    for _ in range(2):  # an over-long draft gets one retry before the cut
        raw = llm.generate(cfg, prompt, options={"temperature": 0.7})
        if raw is None:
            break
        note = _tidy_note(llm.strip_think(raw))
        if len(note) <= NOTE_LIMIT:
            break
        prompt += (f"\n\nYour last draft was {len(note)} characters, over "
                   f"the limit:\n{note}\nShorten the second sentence.")
    return _fit_note(note) or None


def judge_fit(job: Job, profile_text: str, cfg: dict) -> dict | None:
    """Score one job against the profile on four 0-100 dimensions; Python
    weighs them (see fit.py). Returns {"score": 0-10, "fit", "detail"},
    {} if the reply can't be scored, None if the LLM backend is unreachable."""
    goals = str(cfg.get("resume", {}).get("goals", "")).strip()
    career = ("the candidate's stated goals below" if goals
              else "the trajectory in the profile")
    prompt = (
        "Judge how well a remote job fits a candidate, based only on the "
        "profile and the posting. Score each dimension from 0 to 100:\n"
        "- skills: the stack and skills the posting asks for vs the candidate's\n"
        "- experience: seniority, scope and domain vs what the role needs\n"
        "- culture: work style, company stage, remote setup\n"
        "- career: whether the role moves the candidate forward, judged "
        f"against {career}\n"
        "Don't compute an overall score. Reply as JSON only:\n"
        '{"skills": <0-100>, "experience": <0-100>, "culture": <0-100>, '
        '"career": <0-100>, "strengths": ["<up to 3 short lines grounded in '
        'the posting>"], "gaps": ["<up to 3 short lines>"], "missing_skills": '
        '["<up to 5 short skill names the posting wants and the profile '
        'lacks, e.g. Kubernetes>"], "fit": "<one line: why it fits / what to '
        'emphasize>"}\n\n'
        f"CANDIDATE PROFILE:\n{profile_text}\n\n"
        + (f"CAREER GOALS:\n{goals}\n\n" if goals else "")
        + f"JOB\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Description: {job.description}\n"
    )
    raw = llm.generate(cfg, prompt, fmt="json")
    if raw is None:
        return None
    data = parse_json_object(llm.strip_think(raw))
    return score_reply(data, cfg) if data is not None else {}


def rerank_with_resume(jobs: list[Job], profile_text: str, cfg: dict,
                       shortlist: int | None = None,
                       on_progress: Callable[[int, int], None] | None = None,
                       ) -> list[Job]:
    """Re-rank keyword-gated jobs by LLM-judged fit with the resume.

    The top `shortlist` jobs by keyword score (default `[resume].shortlist`)
    are judged, one LLM call each; `on_progress(done, total)` fires after
    each. LLM score is primary, keyword score the tiebreak. Jobs below
    `[resume].min_llm_score` are dropped. If the LLM backend is unreachable
    the stage is a no-op and the keyword order is returned untouched.
    """
    r = cfg.get("resume", {})
    if shortlist is None:
        shortlist = r.get("shortlist", 30)
    floor = r.get("min_llm_score", 5)

    ranked = sorted(jobs, key=lambda j: j.score, reverse=True)
    head, tail = ranked[:shortlist], ranked[shortlist:]

    scored: list[Job] = []
    for i, job in enumerate(head, 1):
        result = judge_fit(job, profile_text, cfg)
        if result is None:  # backend died mid-run: keep the keyword order
            return jobs
        job.llm_score = result.get("score", 0.0)
        job.fit_note = result.get("fit", "")
        job.fit_detail = result.get("detail", {})
        scored.append(job)
        if on_progress:
            on_progress(i, len(head))

    if floor:
        scored = [j for j in scored if (j.llm_score or 0) >= floor]
    scored.sort(key=lambda j: (j.llm_score or 0, j.score), reverse=True)
    return scored + tail
