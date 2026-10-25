
"""Semantic checks for CodeBridge's restricted Python subset.

These tests compare expected expression results without executing
arbitrary source code or generated source strings.
"""

import ast
import operator

import pytest

from codebridge.ir import source_to_ir
from codebridge.python_translator import translate_ir_to_python


SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def evaluate_expression(node, environment):
    """Evaluate only a restricted expression AST using safe operations."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str, type(None))):
            return node.value
        raise ValueError("Unsupported constant")

    if isinstance(node, ast.Name):
        if node.id not in environment:
            raise ValueError(f"Unknown variable: {node.id}")
        return environment[node.id]

    if isinstance(node, ast.BinOp):
        operation = SAFE_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError("Unsupported binary operator")
        return operation(
            evaluate_expression(node.left, environment),
            evaluate_expression(node.right, environment),
        )

    if isinstance(node, ast.UnaryOp):
        operation = SAFE_OPERATORS.get(type(node.op))
        if operation is None:
            raise ValueError("Unsupported unary operator")
        return operation(evaluate_expression(node.operand, environment))

    raise ValueError(f"Unsupported expression: {type(node).__name__}")


def evaluate_supported_function(source, arguments):
    """Interpret a single supported function without exec or eval."""
    module = ast.parse(source)

    if len(module.body) != 1 or not isinstance(module.body[0], ast.FunctionDef):
        raise ValueError("Expected exactly one function definition")

    function = module.body[0]

    if len(function.args.args) != len(arguments):
        raise ValueError("Argument count does not match function parameters")

    environment = {
        parameter.arg: value
        for parameter, value in zip(function.args.args, arguments)
    }

    for statement in function.body:
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1:
                raise ValueError("Multiple assignment targets are unsupported")
            target = statement.targets[0]
            if not isinstance(target, ast.Name):
                raise ValueError("Only simple assignments are supported")
            environment[target.id] = evaluate_expression(
                statement.value, environment
            )

        elif isinstance(statement, ast.Return):
            if statement.value is None:
                return None
            return evaluate_expression(statement.value, environment)

        elif isinstance(statement, ast.Pass):
            continue

        else:
            raise ValueError(
                f"Unsupported statement: {type(statement).__name__}"
            )

    return None


@pytest.mark.parametrize(
    ("source", "arguments"),
    [
        ("def add(a, b):\n    return a + b\n", (3, 4)),
        ("def subtract(a, b):\n    return a - b\n", (9, 2)),
        ("def multiply(a, b):\n    return a * b\n", (6, 7)),
        ("def divide(a, b):\n    return a / b\n", (8, 2)),
        (
            "def calculate(a, b):\n"
            "    result = a * b\n"
            "    return result + 1\n",
            (4, 5),
        ),
        ("def negative(value):\n    return -value\n", (5,)),
    ],
)
def test_generated_python_matches_source_subset(source, arguments):
    ir = source_to_ir(source)
    generated = translate_ir_to_python(ir)["functions"][0]["source"]

    source_result = evaluate_supported_function(source, arguments)
    generated_result = evaluate_supported_function(generated, arguments)

    assert generated_result == source_result
