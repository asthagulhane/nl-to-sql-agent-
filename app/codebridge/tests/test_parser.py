
import pytest

from codebridge.parser import parse_source


def test_parser_extracts_function_and_parameters():
    source = "def add(a, b):\n    return a + b"

    report = parse_source(source)

    assert report["parse_success"] is True
    assert report["language"] == "python"
    assert report["functions"] == [
        {
            "name": "add",
            "line": 1,
            "parameters": ["a", "b"],
            "is_async": False,
        }
    ]


def test_parser_extracts_assignments_and_returns():
    source = (
        "def calculate(price, quantity):\n"
        "    total = price * quantity\n"
        "    return total\n"
    )

    report = parse_source(source)

    assert any(
        item["target"] == "total"
        for item in report["assignments"]
    )
    assert any(
        item["expression"] == "total"
        for item in report["return_statements"]
    )


def test_parser_extracts_imports_and_calls():
    source = (
        "import math\n"
        "from pathlib import Path\n"
        "value = math.sqrt(16)\n"
    )

    report = parse_source(source)

    assert any(
        item["module"] == "math"
        for item in report["imports"]
    )
    assert any(
        item["module"] == "pathlib"
        and item["name"] == "Path"
        for item in report["imports"]
    )
    assert any(
        item["call"] == "math.sqrt"
        for item in report["function_calls"]
    )


def test_parser_rejects_invalid_python_syntax():
    with pytest.raises(SyntaxError):
        parse_source("def broken(:")


def test_parser_rejects_non_string_input():
    with pytest.raises(TypeError, match="source must be a string"):
        parse_source(123)
