
"""API-key authentication and request rate limiting for QueryMind."""

import hmac
import os
import threading
import time

from fastapi import HTTPException, Request


def role_for_api_key(candidate: str | None) -> str:
    """Resolve a role from server-side API keys, never request JSON."""

    if not candidate:
        raise HTTPException(
            status_code=401,
            detail="A valid X-API-Key header is required.",
        )

    configured_keys = (
        ("QUERYMIND_ADMIN_API_KEY", "admin"),
        ("QUERYMIND_ANALYST_API_KEY", "analyst"),
        ("QUERYMIND_VIEWER_API_KEY", "viewer"),
        ("QUERYMIND_API_KEY", "viewer"),
    )

    configured_any = False

    for env_name, role in configured_keys:
        expected = os.getenv(env_name)

        if expected:
            configured_any = True

            if hmac.compare_digest(candidate, expected):
                return role

    if not configured_any:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured on this server.",
        )

    raise HTTPException(
        status_code=401,
        detail="Invalid API key.",
    )


class FixedWindowRateLimiter:
    """Simple per-process rate limiter."""

    def __init__(self, limit: int = 30, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def allow(self, client_id: str) -> bool:
        current_window = int(time.monotonic() // self.window_seconds)

        with self._lock:
            old_window, count = self._buckets.get(
                client_id,
                (current_window, 0),
            )

            if old_window != current_window:
                count = 0

            if count >= self.limit:
                self._buckets[client_id] = (current_window, count)
                return False

            self._buckets[client_id] = (current_window, count + 1)
            return True


try:
    configured_limit = int(
        os.getenv("QUERYMIND_RATE_LIMIT_PER_MINUTE", "30")
    )
except ValueError:
    configured_limit = 30

rate_limiter = FixedWindowRateLimiter(
    limit=max(1, min(configured_limit, 1000))
)


def enforce_rate_limit(request: Request) -> None:
    """Limit requests by client IP address."""

    client_host = request.client.host if request.client else "unknown"

    if not rate_limiter.allow(client_host):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again shortly.",
        )
