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
import re
import sqlite3
import sys
import tomllib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.toml"
DB_PATH = BASE_DIR / "state.db"
OUT_DIR = BASE_DIR / "queues"

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) queue-agent/1.0 (personal job search tool)"


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    tags: list[str] = field(default_factory=list)
    location: str = ""
    score: float = 0.0

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.url}"


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def load_config() -> dict:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


# --------------------------------------------------------------------------- #
# Fetchers (all public endpoints / feeds; no LinkedIn automation)
# --------------------------------------------------------------------------- #

def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_remoteok() -> list[Job]:
    data = json.loads(_get("https://remoteok.com/api"))
    jobs = []
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue  # first element is API metadata
        jobs.append(Job(
            source="remoteok",
            title=item.get("position", ""),
            company=item.get("company", ""),
            url=item.get("url", ""),
            tags=[t.lower() for t in item.get("tags", [])],
            location=item.get("location", ""),
        ))
    return jobs


def fetch_remotive(search_terms: list[str]) -> list[Job]:
    jobs = []
    for term in search_terms:
        q = urllib.parse.quote(term)
        url = f"https://remotive.com/api/remote-jobs?search={q}&limit=50"
        data = json.loads(_get(url))
        for item in data.get("jobs", []):
            jobs.append(Job(
                source="remotive",
                title=item.get("title", ""),
                company=item.get("company_name", ""),
                url=item.get("url", ""),
                tags=[t.lower() for t in item.get("tags", [])],
                location=item.get("candidate_required_location", ""),
            ))
    return jobs


def fetch_wwr(feeds: list[str]) -> list[Job]:
    jobs = []
    for feed_url in feeds:
        root = ET.fromstring(_get(feed_url))
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            if title_el is None or link_el is None:
                continue
            raw = title_el.text or ""
            # WWR titles look like "Company: Job Title"
            company, _, title = raw.partition(":")
            if not title:
                title, company = raw, ""
            jobs.append(Job(
                source="wwr",
                title=title.strip(),
                company=company.strip(),
                url=(link_el.text or "").strip(),
            ))
    return jobs


FETCHERS = {
    "remoteok": lambda cfg: fetch_remoteok(),
    "remotive": lambda cfg: fetch_remotive(cfg["sources"].get("remotive_searches", ["react"])),
    "wwr": lambda cfg: fetch_wwr(cfg["sources"].get("wwr_feeds", [])),
}


# --------------------------------------------------------------------------- #
# Filtering & scoring
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# State (SQLite)
# --------------------------------------------------------------------------- #

def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            uid TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS queued_companies (
            company TEXT PRIMARY KEY,
            last_queued TEXT NOT NULL,
            times_queued INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS queue_items (
            date TEXT NOT NULL,
            uid TEXT NOT NULL,
            source TEXT NOT NULL,
            company TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            note TEXT,
            done INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, uid)
        );
    """)
    return conn


def is_new(conn: sqlite3.Connection, job: Job, cooldown_days: int) -> bool:
    cur = conn.execute("SELECT 1 FROM seen_jobs WHERE uid = ?", (job.uid,))
    if cur.fetchone():
        return False
    cur = conn.execute(
        "SELECT last_queued FROM queued_companies WHERE company = ?",
        (job.company.lower(),),
    )
    row = cur.fetchone()
    if row:
        last = dt.date.fromisoformat(row[0])
        if (dt.date.today() - last).days < cooldown_days:
            return False
    return True


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
                (date, uid, source, company, title, url, location, score, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, uid) DO UPDATE SET
                note = COALESCE(queue_items.note, excluded.note)
        """, (today, j.uid, j.source, j.company, j.title, j.url,
              j.location, j.score, notes.get(j.uid)))
    conn.commit()


# --------------------------------------------------------------------------- #
# LinkedIn search links (built for YOU to click; nothing is fetched)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Optional: draft connection notes with a local model (Ollama)
# --------------------------------------------------------------------------- #

def draft_note(job: Job, cfg: dict) -> str | None:
    o = cfg.get("ollama", {})
    prompt = (
        "Write a LinkedIn connection note under 200 characters, in English. "
        "From: a senior software engineer / tech lead (React, TypeScript, Node.js) "
        "reaching out about a role. Friendly, direct, no agency-speak, no emojis, "
        "no 'I hope this finds you well'. Mention the company naturally.\n\n"
        f"Company: {job.company}\nRole: {job.title}\n\n"
        "Reply with the note text only."
    )
    body = json.dumps({
        "model": o.get("model", "qwen3:4b"),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7},
    }).encode()
    req = urllib.request.Request(
        o.get("url", "http://localhost:11434") + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            note = json.loads(resp.read()).get("response", "").strip().strip('"')
            return note[:200] if note else None
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Pipeline (shared by the CLI below and webapp.py)
# --------------------------------------------------------------------------- #

def collect_jobs(cfg: dict) -> list[Job]:
    """Fetch every enabled source; a dead board logs a warning, not a crash."""
    all_jobs: list[Job] = []
    for name in cfg["sources"].get("enabled", ["remoteok", "remotive"]):
        fetcher = FETCHERS.get(name)
        if not fetcher:
            print(f"[warn] unknown source: {name}", file=sys.stderr)
            continue
        try:
            fetched = fetcher(cfg)
            print(f"[ok] {name}: {len(fetched)} jobs", file=sys.stderr)
            all_jobs.extend(fetched)
        except Exception as e:  # noqa: BLE001 — a dead board shouldn't kill the run
            print(f"[warn] {name} failed: {e}", file=sys.stderr)
    return all_jobs


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


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

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

    queue = select_queue(conn, collect_jobs(cfg), cfg, limit, cooldown)

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
