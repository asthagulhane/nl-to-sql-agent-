import os
import sqlite3
import json
from groq import Groq
from dotenv import load_dotenv
from rag.retriever import get_relevant_schema

load_dotenv()
from rag.retriever import get_relevant_schema
client = Groq(api_key=os.getenv("GROQ_API_KEY"))



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



def generate_sql(question: str, schema: str, error_context: str = "") -> dict:
    correction_note = ""
    if error_context:
        correction_note = f"""
Your previous attempt failed with this error:
{error_context}

Please fix the SQL query to avoid this error.
"""

    prompt = f"""
You are an expert SQL generator. Given a database schema and a question,
generate a SQL query.

Schema:
{schema}
{correction_note}
Question: {question}

Respond with ONLY a JSON object in this exact format, nothing else:
{{
  "sql": "the SQL query here",
  "confidence": a number from 1 to 10 indicating how confident you are this SQL correctly answers the question,
  "reasoning": "one short sentence explaining your confidence level"
}}
"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw_text = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        parsed = {"sql": raw_text, "confidence": 0, "reasoning": "Could not parse structured response."}

    return parsed


def execute_query(sql: str, db_path="sample.db"):
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
    schema = get_relevant_schema(question)
    attempts = []
    error_context = ""

    for attempt_number in range(1, max_retries + 1):
        sql_response = generate_sql(question, schema, error_context)
        sql = sql_response["sql"]
        confidence = sql_response.get("confidence", 0)
        reasoning = sql_response.get("reasoning", "")

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
        "error": f"Failed after {max_retries} attempts.",
        "attempts": attempts
    }


if __name__ == "__main__":
    test_question = "Show me all employees in the Engineering department"
    result = generate_and_run(test_question)
    print("Final result:", result)