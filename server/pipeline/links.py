"""Build the LinkedIn people-search and Google x-ray links for a target,
plus an ATS search for jobs from boards that gate their apply button.

Generates URLs only — the click is human (see the non-negotiable principle).
"""
from __future__ import annotations

import re
import urllib.parse

from sources import Job

# Boards whose apply button can sit behind an account or a paid plan (WWR
# does both); their cards also get a search for the same role on the
# employer's own ATS, where applying is open.
GATED_BOARDS = {"wwr"}
ATS_SITES = ("boards.greenhouse.io", "job-boards.greenhouse.io",
             "jobs.lever.co", "jobs.ashbyhq.com", "apply.workable.com")


def linkedin_people_search(keywords: str) -> str:
    q = urllib.parse.quote(keywords)
    return f"https://www.linkedin.com/search/results/people/?keywords={q}"


def google_xray(company: str, role: str) -> str:
    q = urllib.parse.quote(f'site:linkedin.com/in "{role}" "{company}"')
    return f"https://www.google.com/search?q={q}"


def ats_search(company: str, title: str) -> str:
    # "Vested, Inc." on the board is plain "Vested" on its ATS page
    name = re.sub(r",?\s+(inc|llc|ltd|corp|gmbh)\.?$", "", company.strip(), flags=re.I)
    sites = " OR ".join(f"site:{s}" for s in ATS_SITES)
    q = urllib.parse.quote(f'({sites}) "{name}" "{title}"')
    return f"https://www.google.com/search?q={q}"


def build_links(job: Job, cfg: dict) -> dict[str, str]:
    roles = cfg["targets"].get("people_roles", ["Technical Recruiter", "Engineering Manager"])
    links = {}
    for role in roles:
        links[f"LinkedIn · {role}"] = linkedin_people_search(f"{role} {job.company}")
    links["Google x-ray"] = google_xray(job.company, roles[0])
    if job.source in GATED_BOARDS:
        links["ATS search"] = ats_search(job.company, job.title)
    return links
