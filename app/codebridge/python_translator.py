
"""Generate Python source code from CodeBridge's restricted IR.

The generator never executes generated code. It supports only the
IR expression and statement types explicitly handled below.
"""

import ast
from typing import Any


def expression_to_python(expression: dict[str, Any]) -> str:
    """Render a supported IR expression as Python syntax."""
    if not isinstance(expression, dict):
        raise ValueError("Expression must be a dictionary")

    expression_type = expression.get("type")

    if expression_type == "constant":
        value = expression.get("value")
        if not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("Unsupported constant value")
        return repr(value)

    if expression_type == "variable":
        name = expression.get("name")
        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError("Invalid variable name")
        return name

    if expression_type == "binary_operation":
        operators = {
            "add": "+",
            "subtract": "-",
            "multiply": "*",
            "divide": "/",
            "floor_divide": "//",
            "modulo": "%",
        }

        operator = expression.get("operator")
        if operator not in operators:
            raise ValueError(f"Unsupported binary operator: {operator}")

        left = expression_to_python(expression.get("left"))
        right = expression_to_python(expression.get("right"))
        return f"({left} {operators[operator]} {right})"

    if expression_type == "unary_operation":
        operators = {
            "negate": "-",
            "positive": "+",
        }

        operator = expression.get("operator")
        if operator not in operators:
            raise ValueError(f"Unsupported unary operator: {operator}")

        operand = expression_to_python(expression.get("operand"))
        return f"({operators[operator]}{operand})"

    raise ValueError(f"Unsupported expression type: {expression_type}")


def translate_ir_to_python(ir: dict[str, Any]) -> dict[str, Any]:
    """Generate Python source for functions represented in CodeBridge IR."""
    if not isinstance(ir, dict):
        raise TypeError("ir must be a dictionary")

    if ir.get("ir_version") != "1.0":
        raise ValueError("Unsupported or missing IR version")

    functions = ir.get("functions")
    if not isinstance(functions, list):
        raise ValueError("IR functions must be a list")

    generated_functions = []

    for function in functions:
        if not isinstance(function, dict):
            raise ValueError("Each function must be a dictionary")

        name = function.get("name")
        parameters = function.get("parameters")
        statements = function.get("statements")

        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError("Invalid function name")

        if not isinstance(parameters, list) or not all(
            isinstance(item, str) and item.isidentifier()
            for item in parameters
        ):
            raise ValueError(f"Invalid parameters for function {name}")

        if not isinstance(statements, list):
            raise ValueError(f"Statements for {name} must be a list")

        lines = [f"def {name}({', '.join(parameters)}):"]

        if not statements:
            lines.append("    pass")

        for statement in statements:
            if not isinstance(statement, dict):
                raise ValueError("Each statement must be a dictionary")

            statement_type = statement.get("type")

            if statement_type == "assignment":
                target = statement.get("target")
                if not isinstance(target, str) or not target.isidentifier():
                    raise ValueError("Invalid assignment target")

                value = expression_to_python(statement.get("value"))
                lines.append(f"    {target} = {value}")

            elif statement_type == "return":
                value = statement.get("value")
                if value is None:
                    lines.append("    return")
                else:
                    lines.append(
                        f"    return {expression_to_python(value)}"
                    )

            elif statement_type == "pass":
                lines.append("    pass")

            else:
                raise ValueError(
                    f"Unsupported IR statement type: {statement_type}"
                )

        generated_source = "\n".join(lines) + "\n"

        # Validate syntax only; never execute generated source.
        ast.parse(generated_source)

        generated_functions.append(
            {
                "name": name,
                "source": generated_source,
                "syntax_valid": True,
            }
        )

    return {
        "generator": "CodeBridge Python generator v1",
        "source_ir_version": ir["ir_version"],
        "target_language": "python",
        "functions": generated_functions,
        "execution_performed": False,
    }
