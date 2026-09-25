import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.llm_service import execute_query


class TestExecuteQuery:
    """Tests for the SQL safety check and execution layer."""

    def test_select_query_allowed(self):
        result = execute_query("SELECT * FROM employees")
        assert result["success"] is True

    def test_drop_query_blocked(self):
        result = execute_query("DROP TABLE employees")
        assert result["success"] is False
        assert "Only SELECT" in result["error"]

    def test_delete_query_blocked(self):
        result = execute_query("DELETE FROM employees WHERE id = 1")
        assert result["success"] is False
        assert "Only SELECT" in result["error"]

    def test_update_query_blocked(self):
        result = execute_query("UPDATE employees SET salary = 0")
        assert result["success"] is False
        assert "Only SELECT" in result["error"]

    def test_insert_query_blocked(self):
        result = execute_query("INSERT INTO employees VALUES (99, 'x', 'x', 0)")
        assert result["success"] is False
        assert "Only SELECT" in result["error"]

    def test_invalid_sql_returns_error_not_exception(self):
        result = execute_query("SELECT * FROM nonexistent_table")
        assert result["success"] is False
        assert "error" in result

    def test_case_insensitive_select_check(self):
        result = execute_query("select * from employees")
        assert result["success"] is True

    def test_lowercase_drop_still_blocked(self):
        result = execute_query("drop table employees")
        assert result["success"] is False


class TestGenerateAndRun:
    """Tests for the self-correction retry loop."""

    def test_valid_question_returns_results(self):
        from app.llm_service import generate_and_run
        result = generate_and_run("Show me all employees")
        assert result["final_sql"] is not None
        assert result["results"] is not None

    def test_attempts_are_logged(self):
        from app.llm_service import generate_and_run
        result = generate_and_run("Show me all employees")
        assert len(result["attempts"]) >= 1
        assert result["attempts"][0]["attempt"] == 1