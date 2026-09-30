import json
import os
import re
from datetime import datetime, timezone

AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "audit.log")

# Columns hidden from specific roles. Extend this as the schema grows.
RESTRICTED_COLUMNS = {
    "salary": {"viewer"},
}

MAX_ROWS = 100


def mask_results(results: list, role: str) -> list:
    """Redact restricted columns for the given role. Returns a new list, doesn't mutate input."""
    masked = []
    for row in results:
        new_row = dict(row)
        for column, hidden_for_roles in RESTRICTED_COLUMNS.items():
            if column in new_row and role in hidden_for_roles:
                new_row[column] = "***"
        masked.append(new_row)
    return masked


def enforce_row_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
    """Append a LIMIT clause if the query doesn't already have one."""
    if re.search(r"\blimit\b", sql, re.IGNORECASE):
        return sql
    return sql.rstrip(";").strip() + f" LIMIT {max_rows};"


def log_audit_entry(role: str, question: str, sql: str, row_count: int, success: bool, error: str = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "question": question,
        "sql": sql,
        "row_count": row_count,
        "success": success,
        "error": error,
    }
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")