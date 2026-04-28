"""FlareSolverr client for Cloudflare bypass."""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class FlareSolverrClient:
    """HTTP client for FlareSolverr proxy service."""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url.rstrip("/") if base_url else ""

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _api_url(self) -> str:
        """Return the FlareSolverr API endpoint."""
        url = self.base_url
        if not url.endswith("/v1"):
            url = url.rstrip("/") + "/v1"
        return url

    async def is_available(self) -> bool:
        """Check if FlareSolverr is reachable."""
        if not self.is_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.base_url)
                return resp.status_code == 200
        except Exception:
            return False

    async def get_page(self, url: str, session: str | None = None) -> dict[str, Any]:
        """Fetch a page via FlareSolverr. Returns dict with 'html', 'cookies', 'user_agent'."""
        payload: dict[str, Any] = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
        }
        if session:
            payload["session"] = session

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                self._api_url(),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "ok":
            raise RuntimeError(f"FlareSolverr error: {data.get('message', 'unknown')}")

        solution = data.get("solution", {})
        return {
            "html": solution.get("response", ""),
            "cookies": solution.get("cookies", []),
            "user_agent": solution.get("userAgent", ""),
            "status": solution.get("status", 0),
        }

    async def create_session(self, session_id: str | None = None) -> str:
        """Create a persistent browser session. Returns session ID."""
        payload: dict[str, Any] = {"cmd": "sessions.create"}
        if session_id:
            payload["session"] = session_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._api_url(),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        session = data.get("session", "")
        logger.info("FlareSolverr session created: %s", session)
        return session

    async def destroy_session(self, session_id: str) -> None:
        """Destroy a persistent browser session."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    self._api_url(),
                    json={"cmd": "sessions.destroy", "session": session_id},
                    headers={"Content-Type": "application/json"},
                )
            logger.info("FlareSolverr session destroyed: %s", session_id)
        except Exception as e:
            logger.warning("Failed to destroy FlareSolverr session %s: %s", session_id, e)


flaresolverr = FlareSolverrClient()
