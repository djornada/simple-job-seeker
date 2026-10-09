"""Page renderers, one module per route. GET_ROUTES maps path → renderer.

Add a page by dropping a module here and registering its renderer in
GET_ROUTES (same recipe as sources/REGISTRY).
"""
from __future__ import annotations

from .applications import expired_on, page_applications, render_app
from .board import page_board
from .logform import get_log_form, log_button, log_dialog
from .posting import page_posting
from .profile import page_profile
from .queue import (
    ITEM_SELECT,
    get_build_status,
    get_coverage_status,
    get_note_status,
    log_prompt,
    note_block,
    page_queue,
    render_item,
)
from .stats import page_stats

GET_ROUTES = {
    "/": page_queue,
    "/board": page_board,
    "/applications": page_applications,
    "/posting": page_posting,
    "/stats": page_stats,
    "/profile": page_profile,
    "/log-form": get_log_form,
    "/note-status": get_note_status,
    "/coverage-status": get_coverage_status,
    "/build-status": get_build_status,
}

__all__ = ["GET_ROUTES", "ITEM_SELECT", "expired_on", "get_build_status",
           "get_coverage_status", "get_log_form", "log_button", "log_dialog",
           "log_prompt", "note_block", "page_applications", "page_board",
           "page_posting", "page_profile", "page_queue", "page_stats",
           "render_app", "render_item"]
