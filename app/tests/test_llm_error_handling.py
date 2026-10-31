from app.app.llm_service import classify_llm_error


class FakeProviderError(Exception):
    def __init__(self, status_code=None):
        self.status_code = status_code


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


def test_classifies_ai_timeout_without_exposing_provider_details():
    category, message = classify_llm_error(APITimeoutError("secret internal detail"))

    assert category == "llm_timeout"
    assert "timed out" in message
    assert "secret internal detail" not in message


def test_classifies_ai_rate_limit():
    category, _ = classify_llm_error(FakeProviderError(status_code=429))
    assert category == "llm_rate_limited"


def test_classifies_invalid_ai_credentials():
    category, _ = classify_llm_error(FakeProviderError(status_code=401))
    assert category == "llm_authentication_error"


def test_classifies_ai_permission_error():
    category, _ = classify_llm_error(FakeProviderError(status_code=403))
    assert category == "llm_authentication_error"


def test_classifies_ai_connection_failure():
    category, _ = classify_llm_error(APIConnectionError("private endpoint"))
    assert category == "llm_connection_error"


def test_classifies_ai_provider_outage():
    category, _ = classify_llm_error(FakeProviderError(status_code=503))
    assert category == "llm_provider_error"


def test_classifies_unexpected_ai_failure_safely():
    category, message = classify_llm_error(RuntimeError("secret"))
    assert category == "llm_generation_error"
    assert "secret" not in message
