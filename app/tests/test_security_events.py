from fastapi import HTTPException

from app.app.security import role_for_api_key


def test_invalid_api_key_is_rejected_without_revealing_configured_key(monkeypatch):
    monkeypatch.setenv("QUERYMIND_ADMIN_API_KEY", "super-secret-admin-key")
    monkeypatch.delenv("QUERYMIND_ANALYST_API_KEY", raising=False)
    monkeypatch.delenv("QUERYMIND_VIEWER_API_KEY", raising=False)
    monkeypatch.delenv("QUERYMIND_API_KEY", raising=False)

    try:
        role_for_api_key("wrong-key")
        assert False, "Invalid API key should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 401
        assert "super-secret-admin-key" not in str(exc.detail)


def test_invalid_api_key_records_security_event(monkeypatch):
    from fastapi import HTTPException
    from app.app.security import role_for_api_key, security_events

    monkeypatch.setenv("QUERYMIND_ADMIN_API_KEY", "test-admin-secret")
    monkeypatch.delenv("QUERYMIND_ANALYST_API_KEY", raising=False)
    monkeypatch.delenv("QUERYMIND_VIEWER_API_KEY", raising=False)
    monkeypatch.delenv("QUERYMIND_API_KEY", raising=False)

    before = len(security_events.recent(200))

    try:
        role_for_api_key("definitely-invalid")
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Invalid key should be rejected")

    events = security_events.recent(200)
    new_events = events[:max(0, len(events) - before + 1)]
    assert any(e["event_type"] == "auth_invalid_api_key" for e in events)
    assert all("test-admin-secret" not in str(e) for e in events)
