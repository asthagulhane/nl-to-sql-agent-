from fastapi.testclient import TestClient

import app.main as main


def test_query_requires_api_key(monkeypatch):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "viewer-test-key")
    client = TestClient(main.app)
    response = client.post("/query", json={"question": "Show employee names"})
    assert response.status_code == 401


def test_client_cannot_escalate_role_with_request_json(monkeypatch):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "viewer-test-key")
    captured = {}

    def fake_generate_and_run(question, role="viewer"):
        captured["question"] = question
        captured["role"] = role
        return {"final_sql": "SELECT name FROM employees LIMIT 100;", "results": [{"name": "Ada"}], "attempts": []}

    monkeypatch.setattr(main, "generate_and_run", fake_generate_and_run)
    monkeypatch.setattr(main, "log_audit_entry", lambda **kwargs: None)
    client = TestClient(main.app)
    response = client.post(
        "/query",
        headers={"X-API-Key": "viewer-test-key"},
        json={"question": "  Show employee names  ", "role": "admin"},
    )
    assert response.status_code == 200
    assert captured == {"question": "Show employee names", "role": "viewer"}


def test_query_rejects_oversized_question(monkeypatch):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "viewer-test-key")
    client = TestClient(main.app)
    response = client.post(
        "/query",
        headers={"X-API-Key": "viewer-test-key"},
        json={"question": "x" * 1001},
    )
    assert response.status_code == 413
