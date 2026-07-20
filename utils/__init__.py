"""Shared paths and configuration loading.

Single source of truth for the project's on-disk locations and the
`config.toml` + `.env` loading, kept out of the pipeline modules so both
the CLI and the web UI import them without pulling in the whole agent.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.toml"
ENV_PATH = BASE_DIR / ".env"
DB_PATH = BASE_DIR / "state.db"
OUT_DIR = BASE_DIR / "queues"

__all__ = ["BASE_DIR", "CONFIG_PATH", "ENV_PATH", "DB_PATH", "OUT_DIR",
           "load_config"]


def _load_dotenv() -> None:
    """Populate os.environ from a local .env (KEY=value per line), if present.
    Real environment variables win — .env only fills what isn't already set."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config() -> dict:
    _load_dotenv()
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)
