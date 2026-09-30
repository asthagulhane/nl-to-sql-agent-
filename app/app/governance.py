import json
import os
import re
import sqlite3
from datetime import datetime, timezone


AUDIT_LOG_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "audit.log",
    )
)

MAX_ROWS = 100

VALID_ROLES = {
    "viewer",
    "analyst",
    "admin",
}

# Roles listed here are not allowed to read the column.
RESTRICTED_COLUMNS = {
    "salary": {"viewer"},
}


def normalize_role(role: str) -> str:
    """Return a valid role, defaulting unknown roles to viewer."""

    if not role:
        return "viewer"

    role = role.strip().lower()

    if role not in VALID_ROLES:
        return "viewer"

    return role


def is_column_restricted(column_name: str, role: str) -> bool:
    """Check whether a role is blocked from reading a column."""

    role = normalize_role(role)
    column_name = column_name.lower()

    restricted_roles = RESTRICTED_COLUMNS.get(
        column_name,
        set(),
    )

    return role in restricted_roles


def create_authorizer(role: str):
    """
    Create a SQLite authorization callback.

    Restricted columns are denied while SQLite is
    preparing the SQL statement, before results are returned.
    """

    role = normalize_role(role)

    def authorizer(
        action_code,
        arg1,
        arg2,
        database_name,
        trigger_name,
    ):
        if action_code == sqlite3.SQLITE_READ:
            column_name = arg2

            if (
                column_name
                and is_column_restricted(column_name, role)
            ):
                return sqlite3.SQLITE_DENY

        return sqlite3.SQLITE_OK

    return authorizer


def apply_authorizer(
    connection: sqlite3.Connection,
    role: str,
):
    """Attach role-based authorization to a SQLite connection."""

    connection.set_authorizer(
        create_authorizer(role)
    )


def mask_results(results: list, role: str) -> list:
    """
    Mask sensitive fields as a defense-in-depth layer.
    """

    role = normalize_role(role)

    masked = []

    for row in results:
        new_row = dict(row)

        for column, hidden_for_roles in RESTRICTED_COLUMNS.items():
            if (
                column in new_row
                and role in hidden_for_roles
            ):
                new_row[column] = "***"

        masked.append(new_row)

    return masked


def enforce_row_limit(
    sql: str,
    max_rows: int = MAX_ROWS,
) -> str:
    """Append a LIMIT clause when one is not already present."""

    if re.search(
        r"\blimit\b",
        sql,
        re.IGNORECASE,
    ):
        return sql

    return (
        sql.rstrip(";").strip()
        + f" LIMIT {max_rows};"
    )


def log_audit_entry(
    role: str,
    question: str,
    sql: str,
    row_count: int,
    success: bool,
    error: str = None,
):
    """Append one audit event to the JSONL audit log."""

    role = normalize_role(role)

    entry = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "role": role,
        "question": question,
        "sql": sql,
        "row_count": row_count,
        "success": success,
        "error": error,
    }

    with open(
        AUDIT_LOG_PATH,
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(entry) + "\n"
        )