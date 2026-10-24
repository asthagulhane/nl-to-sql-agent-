"""Security primitives for QueryMind's API and SQL execution boundary.

Roles are derived from server-configured API keys, never from request JSON.
SQLite authorizer callbacks deny every operation except read-only query actions.
"""
from __future__ import annotations

import hmac
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request


def role_for_api_key(candidate: Optional[str]) -> str:
    """Map a supplied API key to a role using server-side configuration."""
    if not candidate:
        raise HTTPException(status_code=401, detail="A valid X-API-Key header is required.")

    configured = (
        ("QUERYMIND_ADMIN_API_KEY", "admin"),
        ("QUERYMIND_ANALYST_API_KEY", "analyst"),
        ("QUERYMIND_VIEWER_API_KEY", "viewer"),
        ("QUERYMIND_API_KEY", "viewer"),
    )
    configured_any = False
    for env_name, role in configured:
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
    raise HTTPException(status_code=401, detail="Invalid API key.")


class FixedWindowRateLimiter:
    """Small per-process fixed-window limiter; use a shared store for multi-worker deployments."""

    def __init__(self, limit: int = 30, window_seconds: int = 60, max_clients: int = 10_000):
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._buckets: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def allow(self, client_id: str, now: Optional[float] = None) -> bool:
        now = time.monotonic() if now is None else now
        window = int(now // self.window_seconds)
        with self._lock:
            if len(self._buckets) >= self.max_clients and client_id not in self._buckets:
                # Drop expired entries before rejecting new client identities.
                self._buckets = {
                    key: value for key, value in self._buckets.items()
                    if value[0] >= window
                }
                if len(self._buckets) >= self.max_clients:
                    return False
            old_window, count = self._buckets.get(client_id, (window, 0))
            if old_window != window:
                count = 0
            if count >= self.limit:
                self._buckets[client_id] = (window, count)
                return False
            self._buckets[client_id] = (window, count + 1)
            return True


try:
    _configured_limit = int(os.getenv("QUERYMIND_RATE_LIMIT_PER_MINUTE", "30"))
except ValueError:
    _configured_limit = 30
rate_limiter = FixedWindowRateLimiter(limit=max(1, min(_configured_limit, 1000)))


def enforce_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client_host):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Try again shortly.")


def create_readonly_authorizer(role: str):
    """Allow only SELECT/read/function actions and preserve column-level governance."""
    from app.app.governance import create_authorizer

    role_authorizer = create_authorizer(role)
    allowed = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }
    recursive_code = getattr(sqlite3, "SQLITE_RECURSIVE", None)
    if recursive_code is not None:
        allowed.add(recursive_code)

    def authorizer(action_code, arg1, arg2, database_name, trigger_name):
        if action_code not in allowed:
            return sqlite3.SQLITE_DENY
        return role_authorizer(action_code, arg1, arg2, database_name, trigger_name)

    return authorizer


def open_readonly_connection(db_path: str | Path, role: str, timeout_seconds: float = 5.0) -> sqlite3.Connection:
    """Open an existing SQLite database in read-only URI mode and install a deny-by-default authorizer."""
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError("Configured database file does not exist.")
    uri = path.as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=timeout_seconds)
    connection.execute("PRAGMA query_only = ON")
    connection.set_authorizer(create_readonly_authorizer(role))
    return connection
