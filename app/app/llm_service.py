import os
import sqlite3
import json

from groq import Groq
from dotenv import load_dotenv

from app.rag.retriever import get_relevant_schema
from app.app.governance import enforce_row_limit


# ---------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------

# llm_service.py is located at:
# app/app/llm_service.py
#
# The .env file containing GROQ_API_KEY is located at:
# app/.env
#
# Build the path explicitly so the application works
# regardless of the directory from which Python is started.

ENV_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".env"
    )
)

load_dotenv(ENV_PATH)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        f"GROQ_API_KEY was not found. Expected it in: {ENV_PATH}"
    )

client = Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------
# Database schema helper
# ---------------------------------------------------------

def get_schema(db_path="sample.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    )

    tables = [
        row[0]
        for row in cursor.fetchall()
    ]

    schema_description = ""

    for table in tables:
        cursor.execute(
            f"PRAGMA table_info({table});"
        )

        columns = cursor.fetchall()

        column_desc = ", ".join(
            [
                f"{col[1]} ({col[2]})"
                for col in columns
            ]
        )

        schema_description += (
            f"Table '{table}': "
            f"columns are {column_desc}\n"
        )

    conn.close()

    return schema_description


# ---------------------------------------------------------
# LLM SQL generation
# ---------------------------------------------------------

def generate_sql(
    question: str,
    schema: str,
    error_context: str = ""
) -> dict:

    correction_note = ""

    if error_context:
        correction_note = f"""
Your previous attempt failed with this error:
{error_context}

Please fix the SQL query to avoid this error.
"""

    prompt = f"""
You are an expert SQL generator.

Given a database schema and a question,
generate a SQL query.

Schema:
{schema}

{correction_note}

Question:
{question}

Respond with ONLY a JSON object in this exact format,
nothing else:

{{
  "sql": "the SQL query here",
  "confidence": a number from 1 to 10 indicating how confident you are this SQL correctly answers the question,
  "reasoning": "one short sentence explaining your confidence level"
}}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )

    raw_text = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    try:
        parsed = json.loads(raw_text)

    except json.JSONDecodeError:
        parsed = {
            "sql": raw_text,
            "confidence": 0,
            "reasoning":
                "Could not parse structured response."
        }

    return parsed


# ---------------------------------------------------------
# SQL execution
# ---------------------------------------------------------

def execute_query(
    sql: str,
    db_path="sample.db"
):

    # Safety layer:
    # Only read-only SELECT queries are permitted.
    if not sql.strip().upper().startswith("SELECT"):
        return {
            "success": False,
            "error":
                "Only SELECT statements are allowed."
        }

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(sql)

        columns = [
            description[0]
            for description in cursor.description
        ]

        rows = cursor.fetchall()

        conn.close()

        results = [
            dict(zip(columns, row))
            for row in rows
        ]

        return {
            "success": True,
            "results": results
        }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": str(e)
        }


# ---------------------------------------------------------
# NL -> SQL -> Governance -> Execution
# ---------------------------------------------------------

def generate_and_run(
    question: str,
    max_retries: int = 3
):

    # Retrieve only the schema relevant
    # to the natural-language question.
    schema = get_relevant_schema(question)

    attempts = []
    error_context = ""

    for attempt_number in range(
        1,
        max_retries + 1
    ):

        sql_response = generate_sql(
            question,
            schema,
            error_context
        )

        sql = sql_response.get("sql", "")

        if not sql:
            return {
                "final_sql": None,
                "results": None,
                "error":
                    "The LLM did not return a SQL query.",
                "attempts": attempts
            }

        # -------------------------------------------------
        # Governance layer
        # -------------------------------------------------
        # Automatically enforce the maximum row limit.
        #
        # Example:
        # SELECT * FROM employees
        #
        # becomes:
        # SELECT * FROM employees LIMIT 100;
        # -------------------------------------------------

        sql = enforce_row_limit(sql)

        confidence = sql_response.get(
            "confidence",
            0
        )

        reasoning = sql_response.get(
            "reasoning",
            ""
        )

        result = execute_query(sql)

        attempts.append({
            "attempt": attempt_number,
            "sql": sql,
            "confidence": confidence,
            "reasoning": reasoning,
            "success": result["success"],
            "error": result.get("error")
        })

        if result["success"]:
            return {
                "final_sql": sql,
                "confidence": confidence,
                "reasoning": reasoning,
                "results": result["results"],
                "attempts": attempts
            }

        error_context = result["error"]

    return {
        "final_sql": None,
        "results": None,
        "error":
            f"Failed after {max_retries} attempts.",
        "attempts": attempts
    }


# ---------------------------------------------------------
# Local test
# ---------------------------------------------------------

if __name__ == "__main__":

    test_question = (
        "Show me all employees "
        "in the Engineering department"
    )

    result = generate_and_run(
        test_question
    )

    print(
        "Final result:",
        result
    )