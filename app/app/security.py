
"""Security primitives for QueryMind's API and SQL execution boundary.

Roles are derived from server-configured API keys, never from request JSON.
SQLite authorizer callbacks deny unauthorized operations.
"""

from __future__ import annotations

import hmac
import os
import sqlite3
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, Request


# ---------------------------------------------------------
# API authentication
# ---------------------------------------------------------

def role_for_api_key(candidate: Optional[str]) -> str:
    """Resolve a role using server-configured API keys."""

    if not candidate:
        security_events.record("auth_missing_api_key", "medium")
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

    security_events.record("auth_invalid_api_key", "high")
    raise HTTPException(
        status_code=401,
        detail="Invalid API key.",
    )


# ---------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------

class FixedWindowRateLimiter:
    """Thread-safe, bounded, per-process fixed-window rate limiter."""

    def __init__(
        self,
        limit: int = 30,
        window_seconds: int = 60,
        max_clients: int = 10_000,
    ):
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self.max_clients = max(1, max_clients)
        self._buckets: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def allow(
        self,
        client_id: str,
        now: Optional[float] = None,
    ) -> bool:
        current_time = time.monotonic() if now is None else now
        current_window = int(current_time // self.window_seconds)

        with self._lock:
            if (
                len(self._buckets) >= self.max_clients
                and client_id not in self._buckets
            ):
                self._buckets = {
                    key: value
                    for key, value in self._buckets.items()
                    if value[0] >= current_window
                }

                if len(self._buckets) >= self.max_clients:
                    return False

            old_window, count = self._buckets.get(
                client_id,
                (current_window, 0),
            )

            if old_window != current_window:
                count = 0

            if count >= self.limit:
                self._buckets[client_id] = (current_window, count)
                return False

            self._buckets[client_id] = (
                current_window,
                count + 1,
            )
            return True


try:
    _configured_limit = int(
        os.getenv("QUERYMIND_RATE_LIMIT_PER_MINUTE", "30")
    )
except ValueError:
    _configured_limit = 30

rate_limiter = FixedWindowRateLimiter(
    limit=max(1, min(_configured_limit, 1000))
)


def enforce_rate_limit(request: Request) -> None:
    """Apply a per-client-IP request limit."""

    client_host = (
        request.client.host
        if request.client
        else "unknown"
    )

    if not rate_limiter.allow(client_host):
        security_events.record(
            "rate_limit_exceeded",
            "high",
            client_host,
        )
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again shortly.",
        )


# ---------------------------------------------------------
# SQLite role-based authorization
# ---------------------------------------------------------

def create_readonly_authorizer(role: str):
    """Combine SQLite read-only restrictions with column-level governance."""

    from app.app.governance import create_authorizer

    role_authorizer = create_authorizer(role)

    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }

    recursive_code = getattr(sqlite3, "SQLITE_RECURSIVE", None)
    if recursive_code is not None:
        allowed_actions.add(recursive_code)

    def authorizer(
        action_code,
        arg1,
        arg2,
        database_name,
        trigger_name,
    ):
        if action_code not in allowed_actions:
            return sqlite3.SQLITE_DENY

        return role_authorizer(
            action_code,
            arg1,
            arg2,
            database_name,
            trigger_name,
        )

    return authorizer


def open_readonly_connection(
    db_path: str | Path,
    role: str,
    timeout_seconds: float = 5.0,
) -> sqlite3.Connection:
    """Open an existing database read-only and install its authorizer."""

    path = Path(db_path).resolve()

    if not path.is_file():
        raise FileNotFoundError(
            "Configured database file does not exist."
        )

    uri = path.as_uri() + "?mode=ro"

    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=timeout_seconds,
    )

    try:
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(create_readonly_authorizer(role))
        return connection
    except Exception:
        connection.close()
        raise


# ---------------------------------------------------------
# Security event tracking
# ---------------------------------------------------------

class SecurityEventTracker:
    """Thread-safe, bounded in-memory security event tracker."""

    def __init__(self, max_events: int = 1000):
        self._events = deque(maxlen=max(1, max_events))
        self._lock = threading.Lock()

    def record(
        self,
        event_type: str,
        severity: str = "medium",
        client_id: str = "unknown",
    ) -> None:
        from datetime import datetime, timezone

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": str(event_type)[:80],
            "severity": (
                severity
                if severity in {"low", "medium", "high", "critical"}
                else "medium"
            ),
            "client_id": str(client_id)[:100],
        }

        with self._lock:
            self._events.append(event)

    def recent(self, limit: int = 50) -> list[dict]:
        limit = max(1, min(limit, 200))

        with self._lock:
            return list(reversed(list(self._events)[-limit:]))


security_events = SecurityEventTracker()
