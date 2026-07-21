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
from .queue import page_queue
from .stats import page_stats

GET_ROUTES = {
    "/": page_queue,
    "/board": page_board,
    "/due": page_due,
    "/log": page_log,
    "/company": page_company,
    "/stats": page_stats,
    "/profile": page_profile,
}

__all__ = ["GET_ROUTES", "page_board", "page_company", "page_due", "page_log",
           "page_profile", "page_queue", "page_stats"]
