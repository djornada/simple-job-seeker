"""
Job sources — one module per provider, uniform `fetch(cfg) -> list[Job]`.

This package is the facade over the individual boards. Add a provider by
dropping a module with a `fetch(cfg)` here and registering it in `REGISTRY`;
enable it in `config.toml` under `[sources] enabled`.

Every source is a public endpoint or feed
"""

from __future__ import annotations

import sys

from . import hn, remoteok, remotive, wwr
from .base import Job, strip_html

REGISTRY = {
    "remoteok": remoteok.fetch,
    "remotive": remotive.fetch,
    "wwr": wwr.fetch,
    "hn": hn.fetch,
}

__all__ = ["Job", "strip_html", "REGISTRY", "collect_jobs"]


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
