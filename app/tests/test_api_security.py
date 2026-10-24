
import pytest
from fastapi.testclient import TestClient

from main import app
from app.security import rate_limiter


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Give every test a fresh rate-limit state."""
    with rate_limiter._lock:
        rate_limiter._buckets.clear()
    yield
    with rate_limiter._lock:
        rate_limiter._buckets.clear()


def test_health_endpoint_is_available(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["version"] == "1.2.0"


def test_missing_api_key_is_rejected(client, monkeypatch):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "test-viewer-key")

    response = client.post(
        "/query",
        json={"question": "Show all employees"},
    )

    assert response.status_code == 401


def test_invalid_api_key_is_rejected(client, monkeypatch):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "test-viewer-key")

    response = client.post(
        "/query",
        headers={"X-API-Key": "wrong-key"},
        json={"question": "Show all employees"},
    )

    assert response.status_code == 401


def test_unrelated_question_does_not_call_sql_pipeline(
    client, monkeypatch
):
    monkeypatch.setenv("QUERYMIND_VIEWER_API_KEY", "test-viewer-key")

    def unexpected_pipeline_call(*args, **kwargs):
        pytest.fail("SQL pipeline must not run for unrelated questions")

    monkeypatch.setattr(
        "main.generate_and_run",
        unexpected_pipeline_call,
    )

    response = client.post(
        "/query",
        headers={"X-API-Key": "test-viewer-key"},
        json={"question": "Write me a poem about the moon"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["category"] == "out_of_scope"


def test_valid_key_uses_server_configured_role(client, monkeypatch):
    monkeypatch.setenv("QUERYMIND_ANALYST_API_KEY", "test-analyst-key")

    def fake_pipeline(question, role):
        assert role == "analyst"
        return {
            "final_sql": "SELECT name FROM employees",
            "results": [{"name": "Alice"}],
            "row_count": 1,
            "error": None,
        }

    monkeypatch.setattr("main.generate_and_run", fake_pipeline)
    monkeypatch.setattr("main.log_audit_entry", lambda **kwargs: None)

    response = client.post(
        "/query",
        headers={"X-API-Key": "test-analyst-key"},
        json={"question": "Show all employees"},
    )

    assert response.status_code == 200
    assert response.json()["results"] == [{"name": "Alice"}]
