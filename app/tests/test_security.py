import sqlite3

import pytest
from fastapi import HTTPException

from app.app.security import FixedWindowRateLimiter, open_readonly_connection, role_for_api_key


def test_role_is_derived_from_server_config(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ADMIN_API_KEY", "admin-test-key")
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "viewer-test-key")
    assert role_for_api_key("admin-test-key") == "admin"
    assert role_for_api_key("viewer-test-key") == "viewer"
    with pytest.raises(HTTPException) as exc:
        role_for_api_key("not-a-key")
    assert exc.value.status_code == 401


def test_missing_api_key_configuration_fails_closed(monkeypatch):
    for name in ("QUERYMIND_ADMIN_API_KEY", "QUERYMIND_ANALYST_API_KEY",
                 "QUERYMIND_VIEWER_API_KEY", "QUERYMIND_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(HTTPException) as exc:
        role_for_api_key("some-key")
    assert exc.value.status_code == 503


def test_rate_limiter_enforces_fixed_window():
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("client", now=1)
    assert limiter.allow("client", now=2)
    assert not limiter.allow("client", now=3)
    assert limiter.allow("client", now=61)


def test_readonly_connection_blocks_mutation_and_allows_select(tmp_path):
    db = tmp_path / "test.db"
    writer = sqlite3.connect(db)
    writer.execute("CREATE TABLE employees (id INTEGER, name TEXT)")
    writer.execute("INSERT INTO employees VALUES (1, 'Ada')")
    writer.commit()
    writer.close()

    conn = open_readonly_connection(db, "admin")
    try:
        assert conn.execute("SELECT name FROM employees").fetchone() == ("Ada",)
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM employees")
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("PRAGMA user_version")
    finally:
        conn.close()


def test_execute_query_hard_caps_returned_rows(tmp_path):
    from app.app.governance import MAX_ROWS
    from app.app.llm_service import execute_query

    db = tmp_path / "many_rows.db"
    writer = sqlite3.connect(db)
    writer.execute("CREATE TABLE items (id INTEGER PRIMARY KEY)")
    writer.executemany("INSERT INTO items (id) VALUES (?)", [(i,) for i in range(MAX_ROWS + 25)])
    writer.commit()
    writer.close()

    result = execute_query("SELECT id FROM items", db_path=str(db), role="admin")
    assert result["success"] is True
    assert len(result["results"]) == MAX_ROWS
    assert result["truncated"] is True
