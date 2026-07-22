"""Serving the built frontend.

Two things the plain ``StaticFiles`` mount got wrong:

* **Caching.**  ``index.html`` keeps its name while the hashed asset filenames
  change with every build.  A browser that caches it keeps asking for bundles
  that the new container no longer has — a white page and a 404 after every
  add-on update, until the user clears the cache by hand.  So: never cache the
  HTML, cache the content-hashed assets for a year.
* **Client-side routes.**  Reloading (or bookmarking) `/inbox` looked for a
  file of that name and 404'd.  Unknown paths now fall back to ``index.html``
  and let the router take over.
"""
from __future__ import annotations

import logging
from typing import Any

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

INDEX = "index.html"

# Only files below this directory carry a content hash in their name (Vite's
# `assetsDir`), so only those are safe to cache indefinitely.  Everything else
# — index.html, favicon, manifest — keeps a stable name and must revalidate.
HASHED_DIR = "assets/"

NO_CACHE = "no-cache, must-revalidate"
IMMUTABLE = "public, max-age=31536000, immutable"

# Paths that must keep returning their own errors instead of the SPA shell.
API_PREFIXES = ("api/", "mcp")


def _is_api_path(path: str) -> bool:
    return path.startswith(API_PREFIXES)


def _looks_like_a_file(path: str) -> bool:
    """Whether the last path segment names a file (has an extension).

    A missing `.js` must stay a 404: answering it with the HTML shell only
    turns a clear error into a confusing MIME-type failure in the browser.
    """
    return "." in path.rsplit("/", 1)[-1]


class SpaStaticFiles(StaticFiles):
    """StaticFiles with SPA fallback and build-aware cache headers."""

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or _is_api_path(path) or _looks_like_a_file(path):
                raise
            # A client-side route — hand over the shell.
            response = await super().get_response(INDEX, scope)
            path = INDEX

        if response.status_code < 400:
            hashed = path.startswith(HASHED_DIR)
            response.headers["cache-control"] = IMMUTABLE if hashed else NO_CACHE
        return response
