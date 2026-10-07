from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) queue-agent/1.0 (personal job search tool)"


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    tags: list[str] = field(default_factory=list)
    location: str = ""
    score: float = 0.0
    description: str = ""  # full_text[:2000], what the LLM sees
    full_text: str = ""    # untruncated, archived in `postings`
    llm_score: float | None = None
    fit_note: str = ""
    flags: list[str] = field(default_factory=list)  # gate notes, persisted
    gate: str = ""  # "language"/"eligibility" when a gate rejected it

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.url}"


def is_linkedin(url: str) -> bool:
    """linkedin.com or any subdomain. Nothing in this package requests one."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


class _NoLinkedInRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects, except to LinkedIn: stop and surface the 3xx."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if is_linkedin(newurl):
            return None  # urllib then raises HTTPError(code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_NoLinkedInRedirect)


def _get(url: str, timeout: int = 20) -> bytes:
    if is_linkedin(url):
        raise ValueError(f"refusing to fetch a LinkedIn URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _OPENER.open(req, timeout=timeout) as resp:
        return resp.read()


def http_probe(url: str, timeout: int = 20) -> tuple[bool | None, str]:
    """GET the posting: (verdict, final URL after redirects). 404/410 means
    gone (False), 2xx live (True), anything else (403, 5xx, timeout, a
    refused LinkedIn redirect) None, "can't tell". A LinkedIn URL is never
    requested."""
    if is_linkedin(url) or not url.startswith(("http://", "https://")):
        return None, url
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return (True if 200 <= resp.status < 300 else None), resp.geturl()
    except urllib.error.HTTPError as e:
        return (False if e.code in (404, 410) else None), url
    except (OSError, ValueError):  # URLError, timeouts, bad URLs
        return None, url


def http_is_live(url: str) -> bool | None:
    """Default liveness check for a board: `http_probe`'s verdict."""
    return http_probe(url)[0]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(raw: str, limit: int | None = 2000) -> str:
    """HTML to collapsed plain text; `limit=None` keeps all of it."""
    if not raw:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(raw)
    except Exception:  # noqa: BLE001 — malformed markup shouldn't crash a fetch
        return re.sub(r"\s+", " ", raw).strip()[:limit]
    text = re.sub(r"\s+", " ", "".join(parser.parts)).strip()
    return text[:limit]
