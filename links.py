"""Build the LinkedIn people-search and Google x-ray links for a target.

Generates URLs only — the click is human (see the non-negotiable principle).
"""
from __future__ import annotations

import urllib.parse

from sources import Job


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
