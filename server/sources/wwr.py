from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET

from .base import Job, _get, http_probe, strip_html

def is_live(url: str) -> bool | None:
    """WWR answers a missing job with a redirect to its homepage (200), so
    ending up off /remote-jobs/ means the post is gone."""
    verdict, final = http_probe(url)
    path = urllib.parse.urlsplit(final).path
    if verdict and not path.startswith("/remote-jobs/"):
        return False
    return verdict


def fetch(cfg: dict) -> list[Job]:
    feeds = cfg["sources"].get("wwr_feeds", [])
    jobs = []
    for feed_url in feeds:
        root = ET.fromstring(_get(feed_url))
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            if title_el is None or link_el is None:
                continue
            raw = title_el.text or ""
            company, _, title = raw.partition(":")
            if not title:
                title, company = raw, ""
            text = strip_html(desc_el.text if desc_el is not None else "", None)
            jobs.append(Job(
                source="wwr",
                title=title.strip(),
                company=company.strip(),
                url=(link_el.text or "").strip(),
                description=text[:2000],
                full_text=text,
            ))
    return jobs
