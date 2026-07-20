#!/usr/bin/env python3
"""
Daily LinkedIn target queue builder.

Fetches remote job boards (RemoteOK, Remotive, We Work Remotely), filters
roles that match your profile, deduplicates against a local SQLite state,
and emits a daily queue of companies with prebuilt LinkedIn search links.

You do the clicking. The script does the deciding.

Usage:
    python queue_agent.py              # build today's queue
    python queue_agent.py --notes      # also draft connection notes via Ollama
    python queue_agent.py --dry-run    # don't persist state
    python queue_agent.py --stats      # show pipeline stats
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

from db import db_connect, is_new  # noqa: F401 — re-exported as qa.*
from sources import Job, collect_jobs  # noqa: F401
from utils import DB_PATH, OUT_DIR, load_config  # noqa: F401 — re-exported as qa.*


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9+#. ]", " ", text.lower())

def score_job(job: Job, cfg: dict) -> float:
    """Score by keyword matches; return 0 to reject."""
    f = cfg["filters"]
    haystack = _norm(f"{job.title} {' '.join(job.tags)}")
    title = _norm(job.title)

    for bad in f.get("exclude_keywords", []):
        if _norm(bad) in title:
            return 0.0

    if f.get("brazil_friendly_only", False) and job.location:
        loc = job.location.lower()
        ok_markers = ("worldwide", "anywhere", "latam", "latin america",
                      "americas", "brazil", "south america", "global", "remote")
        if not any(m in loc for m in ok_markers):
            return 0.0

    score = 0.0
    matched_role = False
    for kw in f.get("role_keywords", []):
        if _norm(kw) in title:
            score += 3.0
            matched_role = True
    for kw in f.get("stack_keywords", []):
        if _norm(kw) in haystack:
            score += 1.0

    if not matched_role:
        return 0.0
    return score


def mark_queued(conn: sqlite3.Connection, job: Job) -> None:
    today = dt.date.today().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO seen_jobs (uid, first_seen) VALUES (?, ?)",
        (job.uid, today),
    )
    conn.execute("""
        INSERT INTO queued_companies (company, last_queued)
        VALUES (?, ?)
        ON CONFLICT(company) DO UPDATE SET
            last_queued = excluded.last_queued,
            times_queued = times_queued + 1
    """, (job.company.lower(), today))


def save_queue(conn: sqlite3.Connection, queue: list[Job],
               notes: dict[str, str]) -> None:
    """Persist queue items (feeds the web UI) and mark companies queued."""
    today = dt.date.today().isoformat()
    for j in queue:
        mark_queued(conn, j)
        conn.execute("""
            INSERT INTO queue_items
                (date, uid, source, company, title, url, location, score, note,
                 description, fit_note, llm_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, uid) DO UPDATE SET
                note = COALESCE(queue_items.note, excluded.note),
                fit_note = COALESCE(excluded.fit_note, queue_items.fit_note),
                llm_score = COALESCE(excluded.llm_score, queue_items.llm_score)
        """, (today, j.uid, j.source, j.company, j.title, j.url,
              j.location, j.score, notes.get(j.uid),
              j.description, j.fit_note or None, j.llm_score))
    conn.commit()


def linkedin_people_search(keywords: str) -> str:
    q = urllib.parse.quote(keywords)
    return f"https://www.linkedin.com/search/results/people/?keywords={q}"

def google_xray(company: str, role: str) -> str:
    q = urllib.parse.quote(f'site:linkedin.com/in "{role}" "{company}"')
    return f"https://www.google.com/search?q={q}"

def build_links(job: Job, cfg: dict) -> dict[str, str]:
    roles = cfg["targets"].get("people_roles", ["Technical Recruiter", "Engineering Manager"])
    links = {}
    for role in roles:
        links[f"LinkedIn · {role}"] = linkedin_people_search(f"{role} {job.company}")
    links["Google x-ray"] = google_xray(job.company, roles[0])
    return links

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


def _strip_think(text: str) -> str:
    """qwen3 leaks <think>…</think> even with think disabled; drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

def _llm_generate(cfg: dict, prompt: str, *, fmt: str | None = None,
                  options: dict | None = None, timeout: int = 300) -> str | None:
    """One completion from the configured provider.

    `[llm].provider` selects the backend: "ollama" (default, local) or
    "openai" for any OpenAI-compatible chat endpoint (e.g. NVIDIA NIM).
    Returns raw response text, or None if the backend is unreachable.
    """
    provider = cfg.get("llm", {}).get("provider", "ollama").lower()
    if provider in ("openai", "nvidia", "nim"):
        return _openai_generate(cfg, prompt, fmt=fmt, options=options,
                                timeout=timeout)
    return _ollama_generate(cfg, prompt, fmt=fmt, options=options,
                            timeout=timeout)


def _ollama_generate(cfg: dict, prompt: str, *, fmt: str | None = None,
                     options: dict | None = None, timeout: int = 300) -> str | None:
    """One /api/generate call. Returns raw response text, or None if unreachable."""
    o = cfg.get("ollama", {})
    payload: dict = {
        "model": o.get("model", "qwen3:4b"),
        "prompt": prompt,
        "stream": False,
        "think": False,
    }
    if fmt:
        payload["format"] = fmt
    if options:
        payload["options"] = options
    req = urllib.request.Request(
        o.get("url", "http://localhost:11434") + "/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()).get("response", "")
    except OSError:
        return None


def _openai_generate(cfg: dict, prompt: str, *, fmt: str | None = None,
                     options: dict | None = None, timeout: int = 300) -> str | None:
    """One /chat/completions call against an OpenAI-compatible endpoint
    (e.g. NVIDIA NIM). The API key is read from the env var named in
    `[openai].api_key_env` so no secret is committed. Returns the message
    content, or None if the endpoint is unreachable."""
    o = cfg.get("openai", {})
    api_key = os.environ.get(o.get("api_key_env", "OPENAI_API_KEY"), "")
    payload: dict = {
        "model": o.get("model", "z-ai/glm-5.2"),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if options and "temperature" in options:
        payload["temperature"] = options["temperature"]
    if fmt == "json":  # OpenAI/NIM ask for JSON via response_format
        payload["response_format"] = {"type": "json_object"}
    base = o.get("base_url", "https://integrate.api.nvidia.com/v1").rstrip("/")
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
        body = e.read().decode("utf-8", "replace")[:200]
        print(f"[llm] {base} HTTP {e.code}: {body}", file=sys.stderr)
        return None
    except OSError:
        return None
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


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
    raw = _llm_generate(cfg, prompt, options={"temperature": 0.7})
    if raw is None:
        return None
    note = _strip_think(raw).strip().strip('"')
    return note[:200] if note else None


def _llm_fit(job: Job, profile_text: str, cfg: dict) -> dict | None:
    """Score one job against the profile. None = Ollama unreachable."""
    prompt = (
        "Rate how well a remote job fits a candidate, 0-10, based only on the "
        "profile and the posting. Reply as JSON only: "
        '{"score": <integer 0-10>, "fit": "<one line: why it fits / what to '
        'emphasize>"}.\n\n'
        f"CANDIDATE PROFILE:\n{profile_text}\n\n"
        f"JOB\nTitle: {job.title}\nCompany: {job.company}\n"
        f"Description: {job.description}\n"
    )
    raw = _llm_generate(cfg, prompt, fmt="json")
    if raw is None:
        return None
    try:
        data = json.loads(_strip_think(raw))
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
    `[resume].min_llm_score` are dropped. If Ollama is unreachable the stage
    is a no-op and the keyword order is returned untouched.
    """
    r = cfg.get("resume", {})
    shortlist = r.get("shortlist", 30)
    floor = r.get("min_llm_score", 5)

    ranked = sorted(jobs, key=lambda j: j.score, reverse=True)
    head, tail = ranked[:shortlist], ranked[shortlist:]

    scored: list[Job] = []
    for job in head:
        result = _llm_fit(job, profile_text, cfg)
        if result is None:  # Ollama died mid-run: keep the keyword order
            return jobs
        job.llm_score = result.get("score", 0.0)
        job.fit_note = result.get("fit", "")
        scored.append(job)

    if floor:
        scored = [j for j in scored if (j.llm_score or 0) >= floor]
    scored.sort(key=lambda j: (j.llm_score or 0, j.score), reverse=True)
    return scored + tail

def render(queue: list[Job], links: dict[str, dict[str, str]],
           notes: dict[str, str]) -> str:
    today = dt.date.today().isoformat()
    lines = [f"# Daily queue — {today}", ""]
    if not queue:
        lines.append("No new targets today. Widen filters or lower cooldown.")
    for i, job in enumerate(queue, 1):
        lines.append(f"## {i}. {job.company} — {job.title}")
        lines.append(f"- Job post: {job.url}")
        if job.location:
            lines.append(f"- Location: {job.location}")
        if job.llm_score is not None:
            lines.append(f"- Fit score: {job.llm_score:g}/10")
        if job.fit_note:
            lines.append(f"- Fit: {job.fit_note}")
        for label, url in links[job.uid].items():
            lines.append(f"- {label}: {url}")
        if job.uid in notes:
            lines.append(f"- Draft note: {notes[job.uid]}")
        lines.append("")
    lines.append("---")
    lines.append("Checklist per target: visit 2-3 profiles → connect with note → done.")
    return "\n".join(lines)


def show_stats(conn: sqlite3.Connection) -> None:
    jobs = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
    comps = conn.execute("SELECT COUNT(*) FROM queued_companies").fetchone()[0]
    print(f"Jobs seen: {jobs}")
    print(f"Companies queued: {comps}")
    print("\nMost queued companies:")
    for name, n in conn.execute(
        "SELECT company, times_queued FROM queued_companies "
        "ORDER BY times_queued DESC LIMIT 10"
    ):
        print(f"  {n:>2}x  {name}")

def select_queue(conn: sqlite3.Connection, jobs: list[Job], cfg: dict,
                 limit: int, cooldown: int) -> list[Job]:
    """Score, filter, dedupe (one job per company) and cap the queue."""
    for job in jobs:
        job.score = score_job(job, cfg)
    candidates = [j for j in jobs if j.score > 0 and j.company and j.url]
    candidates.sort(key=lambda j: j.score, reverse=True)

    queue: list[Job] = []
    seen_companies: set[str] = set()
    for job in candidates:
        key = job.company.lower()
        if key in seen_companies:
            continue
        if not is_new(conn, job, cooldown):
            continue
        queue.append(job)
        seen_companies.add(key)
        if len(queue) >= limit:
            break
    return queue

def main() -> int:
    ap = argparse.ArgumentParser(description="Build today's LinkedIn target queue.")
    ap.add_argument("--notes", action="store_true", help="draft connection notes via Ollama")
    ap.add_argument("--dry-run", action="store_true", help="don't persist state")
    ap.add_argument("--stats", action="store_true", help="show pipeline stats and exit")
    ap.add_argument("-n", type=int, default=None, help="override queue size")
    args = ap.parse_args()

    cfg = load_config()
    conn = db_connect()

    if args.stats:
        show_stats(conn)
        return 0

    limit = args.n or cfg["targets"].get("per_day", 10)
    cooldown = cfg["targets"].get("company_cooldown_days", 30)

    profile_text = load_profile_text(conn)
    pool = max(limit, cfg.get("resume", {}).get("shortlist", 30)) if profile_text else limit
    candidates = select_queue(conn, collect_jobs(cfg), cfg, pool, cooldown)
    if profile_text:
        candidates = rerank_with_resume(candidates, profile_text, cfg)
    queue = candidates[:limit]

    links = {j.uid: build_links(j, cfg) for j in queue}
    notes: dict[str, str] = {}
    if args.notes:
        for j in queue:
            note = draft_note(j, cfg)
            if note:
                notes[j.uid] = note
            else:
                print(f"[warn] note drafting failed for {j.company} "
                      "(is Ollama running?)", file=sys.stderr)
                break

    output = render(queue, links, notes)
    print(output)

    if not args.dry_run and queue:
        save_queue(conn, queue, notes)
        OUT_DIR.mkdir(exist_ok=True)
        out_file = OUT_DIR / f"{dt.date.today().isoformat()}.md"
        out_file.write_text(output)
        print(f"\n[saved] {out_file}", file=sys.stderr)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
