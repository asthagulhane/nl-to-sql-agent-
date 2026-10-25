
"""Translate CodeBridge IR into readable pseudocode.

This translator handles only the IR operations implemented so far.
It does not execute the source program or claim semantic equivalence.
"""

from typing import Any


def expression_to_text(expression: dict[str, Any]) -> str:
    """Render a supported IR expression as readable text."""
    expression_type = expression.get("type")

    if expression_type == "constant":
        return repr(expression["value"])

    if expression_type == "variable":
        return expression["name"]

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
            raise ValueError(f"Unsupported IR operator: {operator}")

        left = expression_to_text(expression["left"])
        right = expression_to_text(expression["right"])
        return f"({left} {operators[operator]} {right})"

    if expression_type == "unary_operation":
        operators = {
            "negate": "-",
            "positive": "+",
        }

        operator = expression.get("operator")
        if operator not in operators:
            raise ValueError(f"Unsupported IR operator: {operator}")

        operand = expression_to_text(expression["operand"])
        return f"({operators[operator]}{operand})"

    raise ValueError(f"Unsupported IR expression type: {expression_type}")


def translate_ir(ir: dict[str, Any]) -> dict[str, Any]:
    """Translate supported IR into deterministic pseudocode."""
    if not isinstance(ir, dict):
        raise TypeError("ir must be a dictionary")

    if ir.get("ir_version") != "1.0":
        raise ValueError("Unsupported or missing IR version")

    if not isinstance(ir.get("functions"), list):
        raise ValueError("IR functions must be a list")

    translated_functions = []

    for function in ir["functions"]:
        name = function.get("name")
        parameters = function.get("parameters")
        statements = function.get("statements")

        if not isinstance(name, str) or not name.isidentifier():
            raise ValueError("Each function must have a valid name")

        if not isinstance(parameters, list) or not all(
            isinstance(parameter, str) and parameter.isidentifier()
            for parameter in parameters
        ):
            raise ValueError(f"Invalid parameters for function {name}")

        if not isinstance(statements, list):
            raise ValueError(f"Statements for {name} must be a list")

        lines = [f"FUNCTION {name}({', '.join(parameters)})"]

        for statement in statements:
            statement_type = statement.get("type")

            if statement_type == "assignment":
                target = statement.get("target")
                if not isinstance(target, str) or not target.isidentifier():
                    raise ValueError("Assignment target must be a variable name")

                value = expression_to_text(statement["value"])
                lines.append(f"  SET {target} = {value}")

            elif statement_type == "return":
                value = statement.get("value")
                if value is None:
                    lines.append("  RETURN")
                else:
                    lines.append(f"  RETURN {expression_to_text(value)}")

            elif statement_type == "pass":
                lines.append("  NO-OP")

            else:
                raise ValueError(
                    f"Unsupported IR statement type: {statement_type}"
                )

        lines.append("END FUNCTION")
        translated_functions.append(
            {"name": name, "text": "\n".join(lines)}
        )

    return {
        "translator": "CodeBridge deterministic pseudocode v1",
        "source_ir_version": ir["ir_version"],
        "target_language": "codebridge-pseudocode",
        "functions": translated_functions,
    }
