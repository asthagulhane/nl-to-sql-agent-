
"""Rule-based static analysis for Python source code.

The analyser inspects the AST and never executes the source program.
It reports selected risky constructs and unsupported syntax.
"""

import ast
from typing import Any


SUPPORTED_TOP_LEVEL_NODES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Import,
    ast.ImportFrom,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.Expr,
    ast.If,
    ast.For,
    ast.While,
    ast.Return,
    ast.Pass,
)


def analyze_source(source: str) -> dict[str, Any]:
    """Analyse Python source and return findings with line numbers.

    Raises:
        TypeError: If source is not a string.
        SyntaxError: If source cannot be parsed.
    """
    if not isinstance(source, str):
        raise TypeError("source must be a string")

    tree = ast.parse(source)
    findings: list[dict[str, Any]] = []

    def add_finding(
        rule_id: str,
        severity: str,
        message: str,
        node: ast.AST,
    ) -> None:
        findings.append(
            {
                "rule_id": rule_id,
                "severity": severity,
                "message": message,
                "line": getattr(node, "lineno", 1),
            }
        )

    # Check top-level statements against the initial
    # CodeBridge migration subset.
    for node in tree.body:
        if not isinstance(node, SUPPORTED_TOP_LEVEL_NODES):
            add_finding(
                "CB100",
                "warning",
                (
                    "Top-level construct is outside the initial "
                    "CodeBridge migration subset."
                ),
                node,
            )

    # Inspect all AST nodes, including those nested in functions.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"eval", "exec"}:
                    add_finding(
                        "CB001",
                        "high",
                        (
                            f"Use of {node.func.id}() can execute "
                            "dynamically supplied code."
                        ),
                        node,
                    )

                elif node.func.id == "compile":
                    add_finding(
                        "CB002",
                        "medium",
                        (
                            "compile() creates code objects; "
                            "review how the result is used."
                        ),
                        node,
                    )

            elif isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in {
                        "run",
                        "Popen",
                        "call",
                        "check_call",
                        "check_output",
                    }
                ):
                    add_finding(
                        "CB003",
                        "medium",
                        (
                            "Subprocess execution found. Review "
                            "command construction and input handling."
                        ),
                        node,
                    )

        # Identify constructs that our initial translator
        # does not yet support.
        if isinstance(node, (ast.Try, ast.With, ast.AsyncWith)):
            add_finding(
                "CB101",
                "warning",
                (
                    f"{type(node).__name__} is not supported by "
                    "the initial CodeBridge migration subset."
                ),
                node,
            )

        elif isinstance(node, (ast.ClassDef,)):
            add_finding(
                "CB102",
                "warning",
                (
                    "Class definitions are not supported by "
                    "the initial CodeBridge migration subset."
                ),
                node,
            )

    # Stable output makes reports and tests reproducible.
    findings.sort(
        key=lambda item: (
            item["line"],
            item["rule_id"],
            item["message"],
        )
    )

    return {
        "language": "python",
        "analysis_success": True,
        "findings_count": len(findings),
        "findings": findings,
        "disclaimer": (
            "These are limited rule-based findings, not proof "
            "of a vulnerability or a complete security audit."
        ),
    }
