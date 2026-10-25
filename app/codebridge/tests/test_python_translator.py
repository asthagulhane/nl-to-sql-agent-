
import ast
import pytest

from codebridge.ir import source_to_ir
from codebridge.python_translator import translate_ir_to_python


def test_generates_valid_python_function():
    ir = source_to_ir(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    result = translate_ir_to_python(ir)
    generated = result["functions"][0]

    assert result["target_language"] == "python"
    assert generated["syntax_valid"] is True
    assert "def add(a, b):" in generated["source"]
    assert "return (a + b)" in generated["source"]
    ast.parse(generated["source"])


def test_generates_assignment_and_return():
    ir = source_to_ir(
        "def calculate(price, quantity):\n"
        "    total = price * quantity\n"
        "    return total\n"
    )

    generated = translate_ir_to_python(ir)["functions"][0]["source"]

    assert "total = (price * quantity)" in generated
    assert "return total" in generated


def test_generates_empty_return():
    ir = source_to_ir(
        "def finish():\n"
        "    return\n"
    )

    generated = translate_ir_to_python(ir)["functions"][0]["source"]

    assert "    return\n" in generated


def test_rejects_wrong_ir_version():
    with pytest.raises(ValueError, match="IR version"):
        translate_ir_to_python(
            {"ir_version": "2.0", "functions": []}
        )


def test_rejects_unsupported_statement():
    ir = {
        "ir_version": "1.0",
        "functions": [
            {
                "name": "example",
                "parameters": [],
                "statements": [{"type": "if"}],
            }
        ],
    }

    with pytest.raises(ValueError, match="Unsupported IR statement"):
        translate_ir_to_python(ir)


def test_rejects_non_dictionary():
    with pytest.raises(TypeError, match="ir must be a dictionary"):
        translate_ir_to_python([])
