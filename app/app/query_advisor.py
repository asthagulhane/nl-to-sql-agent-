import re
import sqlite3
from typing import Any, Dict, List


def normalize_sql(sql: str) -> str:
    """Normalize SQL before analysis."""
    return sql.strip().rstrip(";")


def is_read_only_query(sql: str) -> bool:
    """
    Allow SELECT queries and CTE queries only.
    The advisor never executes modification statements.
    """
    normalized = normalize_sql(sql).lstrip().upper()

    return (
        normalized.startswith("SELECT")
        or normalized.startswith("WITH")
    )


def get_query_plan(
    sql: str,
    db_path: str = "sample.db",
) -> List[Dict[str, Any]]:
    """
    Run SQLite EXPLAIN QUERY PLAN without executing
    the original query.
    """

    if not is_read_only_query(sql):
        raise ValueError(
            "Query advisor only accepts read-only SQL."
        )

    conn = sqlite3.connect(db_path)

    try:
        cursor = conn.cursor()

        cursor.execute(
            "EXPLAIN QUERY PLAN " + normalize_sql(sql)
        )

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "parent": row[1],
                "notused": row[2],
                "detail": row[3],
            }
            for row in rows
        ]

    finally:
        conn.close()


def find_full_table_scans(
    query_plan: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return plan operations that appear to scan a table."""

    scans = []

    for operation in query_plan:
        detail = operation["detail"].upper()

        if (
            "SCAN " in detail
            and "USING INDEX" not in detail
            and "USING COVERING INDEX" not in detail
        ):
            scans.append(operation)

    return scans


def extract_where_columns(sql: str) -> List[str]:
    """
    Extract simple columns appearing in WHERE predicates.

    This is intentionally conservative. It is not intended
    to replace a full SQL parser.
    """

    normalized = normalize_sql(sql)

    where_match = re.search(
        r"\bWHERE\b(.+?)(?:\bGROUP\s+BY\b|\bORDER\s+BY\b|\bLIMIT\b|$)",
        normalized,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not where_match:
        return []

    where_clause = where_match.group(1)

    matches = re.findall(
        r"(?:\b\w+\.)?(\w+)\s*(?:=|>|<|>=|<=|LIKE|IN\b)",
        where_clause,
        flags=re.IGNORECASE,
    )

    seen = set()
    columns = []

    for column in matches:
        lowered = column.lower()

        if lowered not in seen:
            seen.add(lowered)
            columns.append(column)

    return columns


def extract_primary_table(sql: str) -> str | None:
    """Extract the first table following FROM."""

    match = re.search(
        r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)",
        sql,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return match.group(1)


def build_index_suggestions(
    sql: str,
    full_scans: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """
    Generate conservative index suggestions when a query
    performs a full scan and filters by columns.
    """

    if not full_scans:
        return []

    table = extract_primary_table(sql)
    columns = extract_where_columns(sql)

    if not table or not columns:
        return []

    suggestions = []

    for column in columns:
        index_name = f"idx_{table}_{column}"

        suggestions.append(
            {
                "table": table,
                "column": column,
                "reason": (
                    "The query plan contains a table scan "
                    f"while filtering on '{column}'."
                ),
                "suggested_sql": (
                    f"CREATE INDEX {index_name} "
                    f"ON {table}({column});"
                ),
            }
        )

    return suggestions


def analyze_query(
    sql: str,
    db_path: str = "sample.db",
) -> Dict[str, Any]:
    """
    Analyze a query and return its SQLite query plan,
    detected full scans, and possible index suggestions.

    Important: suggested indexes are NOT automatically
    created.
    """

    try:
        query_plan = get_query_plan(
            sql,
            db_path=db_path,
        )

        full_scans = find_full_table_scans(query_plan)

        suggestions = build_index_suggestions(
            sql,
            full_scans,
        )

        return {
            "success": True,
            "sql": normalize_sql(sql),
            "query_plan": query_plan,
            "full_table_scans": full_scans,
            "index_suggestions": suggestions,
            "has_performance_warning": bool(full_scans),
        }

    except (sqlite3.Error, ValueError) as error:
        return {
            "success": False,
            "sql": normalize_sql(sql),
            "error": str(error),
            "query_plan": [],
            "full_table_scans": [],
            "index_suggestions": [],
            "has_performance_warning": False,
        }