from app.app import llm_service


def test_groq_client_uses_explicit_timeout_and_disables_sdk_retries(monkeypatch):
    captured = {}

    class FakeGroq:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_service, "Groq", FakeGroq)

    llm_service.create_groq_client("test-key")

    assert captured == {
        "api_key": "test-key",
        "timeout": llm_service.LLM_REQUEST_TIMEOUT_SECONDS,
        "max_retries": 0,
    }
    assert llm_service.LLM_REQUEST_TIMEOUT_SECONDS == 20.0
