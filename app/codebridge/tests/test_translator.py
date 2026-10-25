
import pytest

from codebridge.ir import source_to_ir
from codebridge.translator import translate_ir


def test_translator_converts_add_function():
    ir = source_to_ir(
        "def add(a, b):\n"
        "    return a + b\n"
    )

    result = translate_ir(ir)
    text = result["functions"][0]["text"]

    assert "FUNCTION add(a, b)" in text
    assert "RETURN (a + b)" in text
    assert "END FUNCTION" in text


def test_translator_converts_assignment():
    ir = source_to_ir(
        "def calculate(price, quantity):\n"
        "    total = price * quantity\n"
        "    return total\n"
    )

    text = translate_ir(ir)["functions"][0]["text"]

    assert "SET total = (price * quantity)" in text
    assert "RETURN total" in text


def test_translator_handles_empty_return():
    ir = source_to_ir(
        "def finish():\n"
        "    return\n"
    )

    text = translate_ir(ir)["functions"][0]["text"]

    assert "  RETURN\n" in text


def test_translator_rejects_wrong_ir_version():
    with pytest.raises(ValueError, match="IR version"):
        translate_ir({"ir_version": "2.0", "functions": []})


def test_translator_rejects_non_dictionary():
    with pytest.raises(TypeError, match="ir must be a dictionary"):
        translate_ir([])


def test_translator_rejects_unsupported_statement():
    ir = {
        "ir_version": "1.0",
        "functions": [
            {
                "name": "example",
                "parameters": [],
                "statements": [{"type": "while"}],
            }
        ],
    }

    with pytest.raises(ValueError, match="Unsupported IR statement"):
        translate_ir(ir)
