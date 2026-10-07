"""
Job sources — one module per provider, uniform `fetch(cfg) -> list[Job]`.

This package is the facade over the individual boards. Add a provider by
dropping a module with a `fetch(cfg)` here and registering it in `REGISTRY`;
enable it in `config.toml` under `[sources] enabled`.

Every source is a public endpoint or feed.

`LIVENESS` maps a source to its `is_live(url) -> bool | None` check (None:
can't tell), used by `pipeline.expiry` to mark postings that were taken
down. A board without its own uses `http_is_live` (404/410 means gone).
Sources missing here, like the extension's LinkedIn items, are never
checked, and `is_linkedin` guards every request this package makes.
"""

from __future__ import annotations

import sys

from . import hn, remoteok, remotive, wwr
from .base import Job, http_is_live, is_linkedin, strip_html

REGISTRY = {
    "remoteok": remoteok.fetch,
    "remotive": remotive.fetch,
    "wwr": wwr.fetch,
    "hn": hn.fetch,
}

LIVENESS = {
    "remoteok": http_is_live,
    "remotive": http_is_live,
    "wwr": wwr.is_live,
    "hn": hn.is_live,
}

__all__ = ["Job", "LIVENESS", "REGISTRY", "collect_jobs", "http_is_live",
           "is_linkedin", "strip_html"]

def collect_jobs(cfg: dict) -> list[Job]:
    all_jobs: list[Job] = []
    for name in cfg["sources"].get("enabled", ["remoteok", "remotive"]):
        fetcher = REGISTRY.get(name)
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
