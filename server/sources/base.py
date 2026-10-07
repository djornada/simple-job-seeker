from __future__ import annotations

import re
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

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.url}"


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


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
