import json

from fastapi.testclient import TestClient

import app.main as main
import app.app.governance as governance


def test_health_endpoint_reports_service_and_version():
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "QueryMind",
        "version": main.app.version,
    }


def test_audit_writer_creates_missing_parent_directory(tmp_path, monkeypatch):
    audit_path = tmp_path / "nested" / "logs" / "audit.jsonl"
    monkeypatch.setattr(governance, "AUDIT_LOG_PATH", str(audit_path))

    governance.log_audit_entry(
        role="analyst",
        question="Show monthly revenue",
        sql="SELECT 1;",
        row_count=1,
        success=True,
    )

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["role"] == "analyst"
    assert event["question"] == "Show monthly revenue"
    assert event["success"] is True


def test_invalid_api_key_does_not_consume_authenticated_query_quota(monkeypatch):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "viewer-test-key")
    calls = []
    monkeypatch.setattr(main, "enforce_rate_limit", lambda request: calls.append(True))

    response = TestClient(main.app).post(
        "/query",
        headers={"X-API-Key": "not-a-valid-key"},
        json={"question": "Show employee names"},
    )

    assert response.status_code == 401
    assert calls == []
