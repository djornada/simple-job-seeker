from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET

from .base import Job, _get, http_probe, strip_html

_FLAG = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")


def _countries(text: str) -> list[str]:
    """The feed's `country` list ("🇧🇷 Brazil, 🇨🇱 Chile, and 🇺🇾 Uruguay")
    as names. Split on the flags, not on "and": "United Kingdom of Great
    Britain and Northern Ireland" is one country."""
    parts = _FLAG.split(text) if _FLAG.search(text) else text.split(",")
    names = (re.sub(r"[,\s]*(?:\band)?[,\s]*$", "", p.strip()) for p in parts)
    return [n for n in names if n]


def _location(item: ET.Element) -> str:
    """Where the post hires from, for the `brazil_friendly_only` filter.
    The `country` list is the real limit when set: a post can say
    "Anywhere in the World" and still only take US residents (WWR
    geolocks its apply button), so the region is used only without one.
    Brazil goes first so a long list still shows it."""
    region = (item.findtext("region") or "").strip()
    countries = _countries(item.findtext("country") or "")
    if not countries:
        return region
    if "Brazil" in countries:
        countries.remove("Brazil")
        countries.insert(0, "Brazil")
    shown = ", ".join(countries[:3])
    more = len(countries) - 3
    return f"{shown} +{more} more" if more > 0 else shown


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
                location=_location(item),
                description=text[:2000],
                full_text=text,
            ))
    return jobs
