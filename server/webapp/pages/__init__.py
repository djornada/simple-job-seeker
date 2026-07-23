"""Page renderers, one module per route. GET_ROUTES maps path → renderer.

Add a page by dropping a module here and registering its renderer in
GET_ROUTES (same recipe as sources/REGISTRY).
"""
from __future__ import annotations

from .board import page_board
from .company import page_company
from .due import page_due
from .log import page_log
from .profile import page_profile
from .queue import (
    get_build_status,
    get_note_status,
    note_block,
    page_queue,
    render_item,
)
from .stats import page_stats

GET_ROUTES = {
    "/": page_queue,
    "/board": page_board,
    "/due": page_due,
    "/log": page_log,
    "/company": page_company,
    "/stats": page_stats,
    "/profile": page_profile,
    "/note-status": get_note_status,
    "/build-status": get_build_status,
}

__all__ = ["GET_ROUTES", "get_build_status", "note_block", "page_board",
           "page_company", "page_due", "page_log", "page_profile",
           "page_queue", "page_stats", "render_item"]
