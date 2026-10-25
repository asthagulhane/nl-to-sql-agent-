
import pytest

from codebridge.ir import source_to_ir


def test_ir_converts_function_and_return_expression():
    report = source_to_ir(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    function = report["functions"][0]

    assert report["ir_version"] == "1.0"
    assert function["name"] == "add"
    assert function["parameters"] == ["a", "b"]
    assert function["statements"][0]["type"] == "return"
    assert function["statements"][0]["value"]["operator"] == "add"


def test_ir_converts_assignment():
    report = source_to_ir(
        "def calculate(price, quantity):\n"
        "    total = price * quantity\n"
        "    return total\n"
    )

    statements = report["functions"][0]["statements"]

    assert statements[0]["type"] == "assignment"
    assert statements[0]["target"] == "total"
    assert statements[0]["value"]["operator"] == "multiply"


def test_ir_converts_negative_number_expression():
    report = source_to_ir(
        "def get_value():\n"
        "    return -5\n"
    )

    expression = report["functions"][0]["statements"][0]["value"]

    assert expression["type"] == "unary_operation"
    assert expression["operator"] == "negate"


def test_ir_rejects_unsupported_statement():
    with pytest.raises(ValueError, match="Unsupported statement"):
        source_to_ir(
            "def check(value):\n"
            "    if value:\n"
            "        return 1\n"
            "    return 0\n"
        )


def test_ir_rejects_non_string_input():
    with pytest.raises(TypeError, match="source must be a string"):
        source_to_ir(123)


def test_ir_rejects_unsupported_expression():
    with pytest.raises(ValueError, match="Unsupported expression"):
        source_to_ir(
            "def get_value(items):\n"
            "    return items[0]\n"
        )
