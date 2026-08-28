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
* **Where those assets then load from.**  The build references its bundles
  relatively (``./assets/index-abc.js``, Vite's ``base: './'``), so the browser
  resolves them against whatever directory the current URL sits in.  Serving
  the shell for ``/decks/5`` therefore made it ask for ``/decks/assets/…`` —
  a 404 by the rule above, and a white page.  The shell now carries a
  ``<base href>`` pointing at the add-on root, so the depth of the route stops
  mattering.  Under Home Assistant ingress that root is the ingress path, which
  the Supervisor puts in the ``X-Ingress-Path`` header of every request.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, Response
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

#: Set by the Supervisor on every ingress request. Preferred over the
#: `INGRESS_ENTRY` environment variable because it is current: a reinstall
#: changes the token, and the variable is only read at startup.
INGRESS_HEADER = b"x-ingress-path"


def _posix(path: str) -> str:
    """The request path with forward slashes, whatever the OS uses.

    Starlette hands `get_response` an *OS-normalised* path, so on Windows
    `/assets/index-abc.js` arrives as `assets\index-abc.js`. Every prefix test
    below is written with forward slashes, so without this the asset cache
    header and the API passthrough both silently do the wrong thing — and did,
    which is why two tests in this file were red on Windows for weeks while
    green on the Pi.
    """
    normalised = path.replace(os.sep, "/")
    if os.altsep:
        normalised = normalised.replace(os.altsep, "/")
    return normalised


def _is_api_path(path: str) -> bool:
    return _posix(path).startswith(API_PREFIXES)


def _looks_like_a_file(path: str) -> bool:
    """Whether the last path segment names a file (has an extension).

    A missing `.js` must stay a 404: answering it with the HTML shell only
    turns a clear error into a confusing MIME-type failure in the browser.
    """
    return "." in _posix(path).rsplit("/", 1)[-1]


def _ingress_base(scope: Any) -> str:
    """The path the add-on is served under, without a trailing slash.

    Empty outside a Supervisor environment, where the app is served from the
    root and relative assets already resolve correctly at depth zero.
    """
    for name, value in scope.get("headers") or []:
        if name.lower() == INGRESS_HEADER:
            return value.decode("latin-1").rstrip("/")
    from .services.ingress import ingress_base  # env fallback, set by run.sh

    return ingress_base()


#: Where the tag goes, in order of preference. Anchoring on `<head>` alone
#: would fail silently on a document that has none — and a base that is not
#: there looks exactly like a base that did not help.
_INSERT_AFTER = (re.compile(r"<head[^>]*>", re.I), re.compile(r"<html[^>]*>", re.I))


def _with_base_href(html: str, base: str) -> str:
    """Insert `<base href="…/">` as early in the document as possible, once.

    A document that already declares a base is left alone: the first `<base>`
    wins in every browser, so appending a second would be a silent no-op that
    reads like a fix.
    """
    if not base or re.search(r"<base[\s>]", html, re.I):
        return html
    tag = f'<base href="{base}/">'
    for pattern in _INSERT_AFTER:
        match = pattern.search(html)
        if match:
            return html[: match.end()] + tag + html[match.end():]
    return tag + html


class SpaStaticFiles(StaticFiles):
    """StaticFiles with SPA fallback, cache headers and an ingress-aware base."""

    async def get_response(self, path: str, scope: Any) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or _is_api_path(path) or _looks_like_a_file(path):
                raise
            # A client-side route — hand over the shell.
            response = await super().get_response(INDEX, scope)
            path = INDEX

        if _posix(path) == INDEX and response.status_code < 400:
            response = self._shell(scope)

        if response.status_code < 400:
            hashed = _posix(path).startswith(HASHED_DIR)
            response.headers["cache-control"] = IMMUTABLE if hashed else NO_CACHE
        return response

    def _shell(self, scope: Any) -> Response:
        """`index.html` with the base href for this request."""
        # `self.directory` is whatever was passed to the mount — a str here.
        source = Path(self.directory or ".") / INDEX
        html = _with_base_href(
            source.read_text(encoding="utf-8"), _ingress_base(scope)
        )
        return HTMLResponse(html)
