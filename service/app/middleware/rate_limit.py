"""Per-IP sliding window rate limiter.

In-memory — resets on service restart. Fine for single-instance Cloud Run.
This is a lightweight defense until IAP lands in Phase 5B.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter keyed by client IP and exact path.

    Parameters
    ----------
    rules : dict[str, int]
        Mapping of exact path → max requests per window.
        Example: ``{"/api/upload": 5, "/api/chat": 20}``
        Only requests whose path matches exactly are throttled.
        Sub-paths like ``/api/upload/status`` are NOT affected.
    window_seconds : int
        Sliding window duration (default 60).
    """

    def __init__(
        self,
        app: object,
        *,
        rules: dict[str, int],
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.rules = rules
        self.window_seconds = window_seconds
        # {(ip, path): deque of timestamps}
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _match_rule(self, path: str) -> tuple[str, int] | None:
        """Return the matching (path, limit) or None.  Exact match only."""
        for rule_path, limit in self.rules.items():
            if path == rule_path:
                return rule_path, limit
        return None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        match = self._match_rule(request.url.path)
        if match is None:
            return await call_next(request)

        prefix, limit = match
        client_ip = request.client.host if request.client else "unknown"
        key = (client_ip, prefix)
        now = time.monotonic()
        window_start = now - self.window_seconds

        timestamps = self._hits[key]
        # Evict expired entries
        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()

        if len(timestamps) >= limit:
            retry_after = int(timestamps[0] - window_start) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        return await call_next(request)
