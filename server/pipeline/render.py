"""Markdown rendering of the daily queue, and the pipeline stats printout."""
from __future__ import annotations

import datetime as dt
import sqlite3

from sources import Job


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
        d = job.fit_detail
        if d:
            dims = ", ".join(f"{k} {v:g}"
                             for k, v in d.get("dimensions", {}).items())
            lines.append(f"- Verdict: {d.get('verdict')} "
                         f"({d.get('overall', 0):g}/100)"
                         + (f" — {dims}" if dims else ""))
        if job.fit_note:
            lines.append(f"- Fit: {job.fit_note}")
        for key, label in (("strengths", "Strength"), ("gaps", "Gap")):
            for item in d.get(key, []) if d else []:
                lines.append(f"- {label}: {item}")
        if d and d.get("missing_skills"):
            lines.append(f"- Missing skills: {', '.join(d['missing_skills'])}")
        if job.flags:
            lines.append(f"- Flags: {'; '.join(job.flags)}")
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
