
"""Parse Python source code into a safe, structured AST report.

This module parses source code but never executes it.
"""

import ast
from typing import Any


def parse_source(source: str) -> dict[str, Any]:
    """Parse Python source and return a JSON-compatible structure.

    Raises:
        TypeError: If source is not a string.
        SyntaxError: If source contains invalid Python syntax.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")

    tree = ast.parse(source)

    functions = []
    imports = []
    assignments = []
    return_statements = []
    function_calls = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "parameters": [
                        arg.arg for arg in node.args.args
                    ],
                    "is_async": isinstance(
                        node, ast.AsyncFunctionDef
                    ),
                }
            )

        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "module": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.append(
                    {
                        "module": node.module or "",
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )

            for target in targets:
                assignments.append(
                    {
                        "target": ast.unparse(target),
                        "line": node.lineno,
                    }
                )

        elif isinstance(node, ast.Return):
            return_statements.append(
                {
                    "line": node.lineno,
                    "expression": (
                        ast.unparse(node.value)
                        if node.value is not None
                        else None
                    ),
                }
            )

        elif isinstance(node, ast.Call):
            function_calls.append(
                {
                    "call": ast.unparse(node.func),
                    "line": node.lineno,
                }
            )

    functions.sort(key=lambda item: item["line"])
    imports.sort(key=lambda item: item["line"])
    assignments.sort(key=lambda item: item["line"])
    return_statements.sort(key=lambda item: item["line"])
    function_calls.sort(key=lambda item: item["line"])

    return {
        "language": "python",
        "parse_success": True,
        "functions": functions,
        "imports": imports,
        "assignments": assignments,
        "return_statements": return_statements,
        "function_calls": function_calls,
    }
