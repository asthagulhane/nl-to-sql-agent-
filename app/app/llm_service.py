
import os
import re
import sqlite3
import json
import time
from pathlib import Path

from groq import Groq
from dotenv import load_dotenv
from app.rag.retriever import get_relevant_schema

from app.app.governance import enforce_row_limit, MAX_ROWS
from app.app.security import open_readonly_connection
from app.app.semantic_layer import build_semantic_context


# ---------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------

DATABASE_PATH = str(
    Path(__file__).resolve().parents[1] / "sample.db"
)

ENV_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", ".env")
)

load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY was not found. "
        "Check the project's .env configuration."
    )

client = Groq(api_key=GROQ_API_KEY)

MODEL_NAME = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_SQL_LENGTH = 20_000


# ---------------------------------------------------------
# Database schema helper
# ---------------------------------------------------------

def get_schema(db_path=DATABASE_PATH):
    """Read schema metadata from an existing SQLite database."""

    database_uri = Path(db_path).resolve().as_uri() + "?mode=ro"

    conn = sqlite3.connect(
        database_uri,
        uri=True,
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )

    try:
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )

        tables = [row[0] for row in cursor.fetchall()]
        descriptions = []

        for table in tables:
            quoted_table = '"' + table.replace('"', '""') + '"'
            cursor.execute(f"PRAGMA table_info({quoted_table})")
            columns = cursor.fetchall()

            column_desc = ", ".join(
                f"{col[1]} ({col[2]})"
                for col in columns
            )

            descriptions.append(
                f"Table '{table}': columns are {column_desc}"
            )

        return "\n".join(descriptions)

    finally:
        conn.close()


# ---------------------------------------------------------
# SQL response validation
# ---------------------------------------------------------

def validate_sql_candidate(sql: str) -> tuple[bool, str]:
    """
    Perform preliminary SQL validation.

    These checks are defense in depth, not a complete SQL parser.
    Database-level read-only and authorization controls are still
    required before executing any generated SQL.
    """

    if not isinstance(sql, str) or not sql.strip():
        return False, "The generated SQL query is empty."

    if len(sql) > MAX_SQL_LENGTH:
        return False, "The generated SQL query is too long."

    statement = sql.strip()

    # Permit one optional trailing semicolon.
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()

    if ";" in statement:
        return False, "Multiple SQL statements are not allowed."

    # Remove leading SQL comments before checking the first keyword.
    while statement:
        statement = statement.lstrip()

        if statement.startswith("--"):
            newline = statement.find("\n")
            if newline == -1:
                return False, "No SQL statement was found."
            statement = statement[newline + 1:]
            continue

        if statement.startswith("/*"):
            comment_end = statement.find("*/", 2)
            if comment_end == -1:
                return False, "Malformed SQL comment."
            statement = statement[comment_end + 2:]
            continue

        break

    if not statement:
        return False, "No SQL statement was found."

    if not re.match(r"(?is)^(SELECT|WITH)\b", statement):
        return False, "Only read-only SELECT queries are allowed."

    forbidden = re.compile(
        r"\b("
        r"INSERT|UPDATE|DELETE|REPLACE|"
        r"CREATE|ALTER|DROP|"
        r"ATTACH|DETACH|"
        r"PRAGMA|VACUUM|REINDEX|"
        r"BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE"
        r")\b",
        re.IGNORECASE,
    )

    if forbidden.search(statement):
        return False, "The SQL contains a prohibited operation."

    return True, ""


# ---------------------------------------------------------
# LLM SQL generation
# ---------------------------------------------------------

def generate_sql(
    question: str,
    schema: str,
    error_context: str = "",
    role: str = "viewer",
) -> dict:

    semantic_context = build_semantic_context(question)

    if not semantic_context:
        semantic_context = (
            "No approved business definition matched this question."
        )

    correction_note = ""

    if error_context:
        correction_note = f"""
The previous SQL attempt failed with this error:
{error_context}

Correct the SQL while preserving the user's original intent.
Do not attempt to bypass access controls.
"""

    prompt = f"""
You are QueryMind, a careful read-only SQL generation system.

Generate one SQLite SELECT query that answers the user's question.

DATABASE SCHEMA:
{schema}

APPROVED BUSINESS DEFINITIONS:
{semantic_context}

SECURITY RULES:
- Generate exactly one read-only SELECT statement.
- Read-only common table expressions (CTEs) are permitted.
- Never generate modifying or administrative SQL statements.
- Never attempt to bypass database authorization.
- The caller's role is {role}.
- Do not request restricted columns for unauthorized roles.
- Avoid SELECT * when specific columns can answer the question.
- Follow approved business definitions when applicable.
- Do not invent tables, columns, or business definitions.
- If the schema cannot answer the question, explain this in reasoning.
- Return valid JSON only.

{correction_note}

USER QUESTION:
{question}

Return this JSON structure:
{{
  "sql": "one SQL SELECT statement",
  "confidence": 1,
  "reasoning": "brief explanation"
}}

Confidence must be an integer from 1 to 10.
"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    raw_text = (
        response.choices[0].message.content or ""
    ).strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "sql": "",
            "confidence": 0,
            "reasoning": "The model returned invalid JSON.",
        }

    if not isinstance(parsed, dict):
        return {
            "sql": "",
            "confidence": 0,
            "reasoning": "The model returned an invalid response structure.",
        }

    sql = parsed.get("sql", "")
    confidence = parsed.get("confidence", 0)
    reasoning = parsed.get("reasoning", "")

    if not isinstance(sql, str):
        sql = ""

    try:
        confidence = max(0, min(10, int(confidence)))
    except (TypeError, ValueError):
        confidence = 0

    if not isinstance(reasoning, str):
        reasoning = ""

    return {
        "sql": sql,
        "confidence": confidence,
        "reasoning": reasoning[:1000],
    }


# ---------------------------------------------------------
# SQL execution with governance
# ---------------------------------------------------------

def execute_query(
    sql: str,
    db_path=DATABASE_PATH,
    role: str = "viewer",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
):
    """Execute a bounded, read-only query using role-based security."""

    valid, validation_error = validate_sql_candidate(sql)

    if not valid:
        return {
            "success": False,
            "error": validation_error,
            "error_type": "query_not_allowed",
        }

    if not os.path.isfile(db_path):
        return {
            "success": False,
            "error": "The configured database file does not exist.",
            "error_type": "database_unavailable",
        }

    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
        or timeout_seconds > 60
    ):
        return {
            "success": False,
            "error": "Query timeout must be greater than 0 and at most 60 seconds.",
            "error_type": "configuration_error",
        }

    conn = None
    timed_out = False

    try:
        # This helper must open SQLite read-only and apply role-based
        # authorization at the database layer.
        conn = open_readonly_connection(
            db_path,
            role,
            timeout_seconds=min(float(timeout_seconds), 5.0),
        )

        start_time = time.monotonic()

        def progress_handler():
            nonlocal timed_out

            if time.monotonic() - start_time >= timeout_seconds:
                timed_out = True
                return 1

            return 0

        conn.set_progress_handler(progress_handler, 1000)

        cursor = conn.cursor()
        bounded_sql = enforce_row_limit(sql, max_rows=MAX_ROWS + 1)
        cursor.execute(bounded_sql)

        if cursor.description is None:
            return {
                "success": False,
                "error": "Query did not produce a result set.",
                "error_type": "query_not_allowed",
            }

        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]

        results = [
            dict(zip(columns, row))
            for row in rows
        ]

        return {
            "success": True,
            "results": results,
            "truncated": truncated,
            "row_count": len(results),
        }

    except sqlite3.Error as error:
        if timed_out:
            return {
                "success": False,
                "error": (
                    f"Query execution exceeded {timeout_seconds} seconds."
                ),
                "error_type": "query_timeout",
            }

        message = str(error).lower()

        if any(
            marker in message
            for marker in (
                "not authorized",
                "prohibited",
                "authorization denied",
                "access to",
            )
        ):
            return {
                "success": False,
                "error": "The requested query is not authorized for this role.",
                "error_type": "authorization_denied",
            }

        return {
            "success": False,
            "error": "The query could not be executed safely.",
            "error_type": "sql_execution_error",
        }

    except (OSError, ValueError) as error:
        return {
            "success": False,
            "error": "The database could not be opened safely.",
            "error_type": "database_unavailable",
        }

    finally:
        if conn is not None:
            conn.set_progress_handler(None, 0)
            conn.close()


# ---------------------------------------------------------
# End-to-end question handling
# ---------------------------------------------------------

def generate_and_run(
    question: str,
    role: str = "viewer",
    max_retries: int = 3,
):
    """Generate SQL, validate it, and execute with bounded retries."""

    if not isinstance(question, str) or not question.strip():
        return {
            "final_sql": None,
            "results": None,
            "error": "Please enter a non-empty question.",
            "error_type": "invalid_question",
            "attempts": [],
        }

    if (
        not isinstance(max_retries, int)
        or isinstance(max_retries, bool)
        or not 1 <= max_retries <= 3
    ):
        return {
            "final_sql": None,
            "results": None,
            "error": "max_retries must be between 1 and 3.",
            "error_type": "configuration_error",
            "attempts": [],
        }

    try:
        schema = get_relevant_schema(question)
    except Exception:
        return {
            "final_sql": None,
            "results": None,
            "error": "Schema retrieval failed. Please try again later.",
            "error_type": "schema_retrieval_error",
            "attempts": [],
        }

    attempts = []
    error_context = ""

    for attempt_number in range(1, max_retries + 1):
        try:
            sql_response = generate_sql(
                question=question,
                schema=schema,
                error_context=error_context,
                role=role,
            )
        except Exception:
            return {
                "final_sql": None,
                "results": None,
                "error": "SQL generation failed. Please try again later.",
                "error_type": "generation_error",
                "attempts": attempts,
            }

        sql = sql_response.get("sql", "")

        if not sql:
            return {
                "final_sql": None,
                "results": None,
                "error": "The model did not return a valid SQL query.",
                "error_type": "generation_error",
                "attempts": attempts,
            }

        valid, validation_error = validate_sql_candidate(sql)

        if not valid:
            attempts.append({
                "attempt": attempt_number,
                "success": False,
                "error_type": "query_not_allowed",
            })

            return {
                "final_sql": None,
                "results": None,
                "error": validation_error,
                "error_type": "query_not_allowed",
                "attempts": attempts,
            }

        result = execute_query(sql, role=role)

        attempts.append({
            "attempt": attempt_number,
            "sql": sql,
            "confidence": sql_response.get("confidence", 0),
            "reasoning": sql_response.get("reasoning", ""),
            "success": result["success"],
            "error_type": result.get("error_type"),
        })

        if result["success"]:
            return {
                "final_sql": sql,
                "confidence": sql_response.get("confidence", 0),
                "reasoning": sql_response.get("reasoning", ""),
                "results": result["results"],
                "truncated": result.get("truncated", False),
                "row_count": result.get(
                    "row_count", len(result["results"])
                ),
                "attempts": attempts,
            }

        error_type = result.get("error_type")

        # Don't retry security, timeout, or configuration failures.
        if error_type in {
            "query_timeout",
            "authorization_denied",
            "query_not_allowed",
            "database_unavailable",
            "configuration_error",
        }:
            return {
                "final_sql": sql,
                "results": None,
                "error": result["error"],
                "error_type": error_type,
                "attempts": attempts,
            }

        error_context = result["error"]

    return {
        "final_sql": None,
        "results": None,
        "error": (
            "The query could not be completed after the allowed attempts."
        ),
        "error_type": "max_retries_exceeded",
        "attempts": attempts,
    }


if __name__ == "__main__":
    test_question = "Show me employees in the Engineering department"

    print(
        json.dumps(
            generate_and_run(test_question, role="viewer"),
            indent=2,
            default=str,
        )
    )


