
import pytest

from codebridge.analyzer import analyze_source


def test_analyzer_detects_eval():
    report = analyze_source(
        "def run(value):\n"
        "    return eval(value)\n"
    )

    findings = [
        finding
        for finding in report["findings"]
        if finding["rule_id"] == "CB001"
    ]

    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["line"] == 2


def test_analyzer_detects_exec():
    report = analyze_source("exec('x = 1')")

    assert any(
        finding["rule_id"] == "CB001"
        for finding in report["findings"]
    )


def test_analyzer_flags_try_as_unsupported():
    source = (
        "def load_data():\n"
        "    try:\n"
        "        return 1\n"
        "    except ValueError:\n"
        "        return 0\n"
    )

    report = analyze_source(source)

    assert any(
        finding["rule_id"] == "CB101"
        and finding["line"] == 2
        for finding in report["findings"]
    )


def test_analyzer_flags_class_definitions():
    report = analyze_source(
        "class Example:\n"
        "    pass\n"
    )

    assert any(
        finding["rule_id"] == "CB102"
        for finding in report["findings"]
    )


def test_clean_supported_function_has_no_findings():
    report = analyze_source(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    assert report["analysis_success"] is True
    assert report["findings_count"] == 0
    assert report["findings"] == []


def test_analyzer_rejects_invalid_syntax():
    with pytest.raises(SyntaxError):
        analyze_source("def broken(:")


def test_analyzer_rejects_non_string_input():
    with pytest.raises(TypeError, match="source must be a string"):
        analyze_source(123)
