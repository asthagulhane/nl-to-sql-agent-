"""
Semantic business layer for QueryMind.
"""

from typing import Dict, List


BUSINESS_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "active employee": {
        "description": "An employee whose status is active.",
        "sql_rule": "employees.status = 'active'",
    },
    "engineering employee": {
        "description": "An employee who belongs to the Engineering department.",
        "sql_rule": "employees.department = 'Engineering'",
    },
    "high salary employee": {
        "description": "An employee whose salary is greater than 100000.",
        "sql_rule": "employees.salary > 100000",
    },
}


def get_matching_definitions(question: str) -> List[Dict[str, str]]:
    normalized_question = question.lower()
    matches = []

    for term, definition in BUSINESS_DEFINITIONS.items():
        if term.lower() in normalized_question:
            matches.append({
                "term": term,
                "description": definition["description"],
                "sql_rule": definition["sql_rule"],
            })

    return matches


def build_semantic_context(question: str) -> str:
    matches = get_matching_definitions(question)

    if not matches:
        return ""

    lines = [
        "Approved business definitions:",
        "",
    ]

    for definition in matches:
        lines.append(
            f"- {definition['term']}: {definition['description']}"
        )
        lines.append(
            f"  Required SQL rule: {definition['sql_rule']}"
        )

    lines.extend([
        "",
        "Use these approved definitions when generating SQL.",
        "Do not replace them with your own interpretation.",
    ])

    return "\n".join(lines)
