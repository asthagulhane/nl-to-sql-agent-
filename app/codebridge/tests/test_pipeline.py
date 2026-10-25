
import ast
import pytest

from codebridge.pipeline import process_source


def test_pipeline_completes_supported_function():
    report = process_source(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    assert report["tool"] == "CodeBridge"
    assert report["version"] == "0.2.0"
    assert report["status"] == "translation_complete"
    assert report["parse"]["parse_success"] is True
    assert report["analysis"]["findings_count"] == 0
    assert report["ir"]["functions"][0]["name"] == "add"

    assert "RETURN (a + b)" in report["translation"]["functions"][0]["text"]

    generated = report["python_translation"]["functions"][0]
    assert generated["syntax_valid"] is True
    assert "def add(a, b):" in generated["source"]
    ast.parse(generated["source"])


def test_pipeline_reports_unsupported_translation():
    report = process_source(
        "def check(value):\n"
        "    if value:\n"
        "        return 1\n"
        "    return 0\n"
    )

    assert report["parse"]["parse_success"] is True
    assert report["translation"] is None
    assert report["python_translation"] is None
    assert report["status"] == "analysis_complete_translation_unsupported"
    assert "If" in report["translation_error"]


def test_pipeline_rejects_invalid_syntax():
    with pytest.raises(SyntaxError):
        process_source("def broken(:")


def test_pipeline_rejects_non_string_input():
    with pytest.raises(TypeError, match="source must be a string"):
        process_source(123)
