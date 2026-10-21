"""Shared by the backends: the error `complete` raises on an HTTP failure."""
from __future__ import annotations


class LLMError(Exception):
    """The endpoint answered with an HTTP error; the message carries the
    status and the start of the body (401 bad key, 404 unknown model…)."""
