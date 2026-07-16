from __future__ import annotations

import xml.etree.ElementTree as ET

from .base import Job, _get, strip_html

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
            jobs.append(Job(
                source="wwr",
                title=title.strip(),
                company=company.strip(),
                url=(link_el.text or "").strip(),
                description=strip_html(desc_el.text if desc_el is not None else ""),
            ))
    return jobs
