import os
import sqlite3
import json          # ADD THIS LINE
from google import genai
from dotenv import load_dotenv
load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def get_schema(db_path="sample.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    schema_description = ""
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        column_desc = ", ".join([f"{col[1]} ({col[2]})" for col in columns])
        schema_description += f"Table '{table}': columns are {column_desc}\n"

    conn.close()
    return schema_description


def generate_sql(question: str, schema: str, error_context: str = "") -> str:
    """
    Generates SQL. If error_context is provided, it means a previous attempt
    failed — we include that failure in the prompt so Gemini can fix it.
    """
    correction_note = ""
    if error_context:
        correction_note = f"""
Your previous attempt failed with this error:
{error_context}

Please fix the SQL query to avoid this error.
"""

    prompt = f"""
You are an expert SQL generator. Given a database schema and a question,
return ONLY the raw SQL query — no explanation, no markdown, no code fences.

Schema:
{schema}
{correction_note}
Question: {question}

SQL query:
"""
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )
    sql = response.text.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql


def execute_query(sql: str, db_path="sample.db"):
    """
    Runs the generated SQL against the database.
    Returns a dict with either the results or the error — never crashes the program.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return {"success": False, "error": "Only SELECT statements are allowed."}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)

        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        results = [dict(zip(columns, row)) for row in rows]
        return {"success": True, "results": results}

    except sqlite3.Error as e:
        return {"success": False, "error": str(e)}


def generate_and_run(question: str, max_retries: int = 3):
    """
    The self-correction loop. Tries to generate + execute SQL up to
    max_retries times, feeding each failure back into the next attempt.
    Returns the full attempt history so it's visible what the agent did.
    """
    schema = get_schema()
    attempts = []
    error_context = ""
    for attempt_number in range(1, max_retries + 1):
        sql = generate_sql(question, schema, error_context)
        result = execute_query(sql)

        attempts.append({
            "attempt": attempt_number,
            "sql": sql,
            "success": result["success"],
            "error": result.get("error")
        })

        if result["success"]:
            return {
                "final_sql": sql,
                "results": result["results"],
                "attempts": attempts
            }

        error_context = result["error"]

    return {
        "final_sql": None,
        "results": None,
        "error": f"Failed after {max_retries} attempts.",
        "attempts": attempts
    }
if __name__ == "__main__":
    test_question = "Show me all employees sorted by their hire_date"
    result = generate_and_run(test_question)
    print("Final result:", result)