"""
Development middleware. When settings.debug is True, disable all
HTTP caching so the browser always fetches fresh HTML, CSS, and JS.

In production (DEBUG=false), only the "no-cache for HTML responses"
rule stays — static assets keep the browser cache for speed.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import get_settings

settings = get_settings()


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Prevent the browser from caching dynamic HTML responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        path = request.url.path
        is_static = path.startswith("/static")

        if settings.debug:
            # Dev: no caching at all
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif not is_static:
            # Prod: HTML never cached (data changes), static cached
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response
