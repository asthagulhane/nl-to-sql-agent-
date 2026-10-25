
"""Build a small, JSON-compatible intermediate representation (IR).

This module supports a deliberately limited Python subset and never
executes the source program.
"""

import ast
from typing import Any


SUPPORTED_BINARY_OPERATORS = {
    ast.Add: "add",
    ast.Sub: "subtract",
    ast.Mult: "multiply",
    ast.Div: "divide",
    ast.FloorDiv: "floor_divide",
    ast.Mod: "modulo",
}


def expression_to_ir(node: ast.expr) -> dict[str, Any]:
    """Convert a supported Python expression into IR."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (str, int, float, bool, type(None))):
            return {"type": "constant", "value": node.value}
        raise ValueError("Unsupported constant type")

    if isinstance(node, ast.Name):
        return {"type": "variable", "name": node.id}

    if isinstance(node, ast.BinOp):
        operator_name = SUPPORTED_BINARY_OPERATORS.get(type(node.op))
        if operator_name is None:
            raise ValueError(
                f"Unsupported binary operator: {type(node.op).__name__}"
            )

        return {
            "type": "binary_operation",
            "operator": operator_name,
            "left": expression_to_ir(node.left),
            "right": expression_to_ir(node.right),
        }

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            operator_name = "negate"
        elif isinstance(node.op, ast.UAdd):
            operator_name = "positive"
        else:
            raise ValueError(
                f"Unsupported unary operator: {type(node.op).__name__}"
            )

        return {
            "type": "unary_operation",
            "operator": operator_name,
            "operand": expression_to_ir(node.operand),
        }

    raise ValueError(
        f"Unsupported expression: {type(node).__name__}"
    )


def source_to_ir(source: str) -> dict[str, Any]:
    """Convert supported function definitions into a simple IR document.

    Supports function parameters, simple assignments, and return
    expressions. Unsupported statements raise ValueError.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")

    tree = ast.parse(source)
    functions = []

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            raise ValueError(
                "Only top-level synchronous function definitions are supported"
            )

        parameters = [
            argument.arg for argument in node.args.args
        ]
        statements = []

        for statement in node.body:
            if isinstance(statement, ast.Assign):
                if len(statement.targets) != 1:
                    raise ValueError(
                        "Multiple assignment targets are not supported"
                    )

                target = statement.targets[0]
                if not isinstance(target, ast.Name):
                    raise ValueError(
                        "Assignments must target a simple variable name"
                    )

                statements.append(
                    {
                        "type": "assignment",
                        "target": target.id,
                        "value": expression_to_ir(statement.value),
                        "line": statement.lineno,
                    }
                )

            elif isinstance(statement, ast.Return):
                statements.append(
                    {
                        "type": "return",
                        "value": (
                            expression_to_ir(statement.value)
                            if statement.value is not None
                            else None
                        ),
                        "line": statement.lineno,
                    }
                )

            elif isinstance(statement, ast.Pass):
                statements.append(
                    {"type": "pass", "line": statement.lineno}
                )

            else:
                raise ValueError(
                    "Unsupported statement: "
                    f"{type(statement).__name__} on line {statement.lineno}"
                )

        functions.append(
            {
                "name": node.name,
                "parameters": parameters,
                "statements": statements,
                "line": node.lineno,
            }
        )

    return {
        "ir_version": "1.0",
        "source_language": "python",
        "functions": functions,
    }
