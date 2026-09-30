import pytest

from app.app.llm_service import (
    execute_query,
    generate_and_run,
)
from app.app.governance import (
    enforce_row_limit,
    mask_results,
    normalize_role,
)


# =========================================================
# SQL EXECUTION + SELECT-ONLY SAFETY
# =========================================================

class TestExecuteQuery:

    def test_admin_select_query_allowed(self):
        result = execute_query(
            "SELECT * FROM employees",
            role="admin",
        )

        assert result["success"] is True
        assert result["results"] is not None


    def test_lowercase_select_allowed_for_admin(self):
        result = execute_query(
            "select * from employees",
            role="admin",
        )

        assert result["success"] is True


    def test_drop_query_blocked(self):
        result = execute_query(
            "DROP TABLE employees",
            role="admin",
        )

        assert result["success"] is False
        assert "Only SELECT" in result["error"]


    def test_delete_query_blocked(self):
        result = execute_query(
            "DELETE FROM employees WHERE id = 1",
            role="admin",
        )

        assert result["success"] is False
        assert "Only SELECT" in result["error"]


    def test_update_query_blocked(self):
        result = execute_query(
            "UPDATE employees SET salary = 0",
            role="admin",
        )

        assert result["success"] is False
        assert "Only SELECT" in result["error"]


    def test_insert_query_blocked(self):
        result = execute_query(
            "INSERT INTO employees VALUES (99, 'x', 'x', 0)",
            role="admin",
        )

        assert result["success"] is False
        assert "Only SELECT" in result["error"]


    def test_lowercase_drop_still_blocked(self):
        result = execute_query(
            "drop table employees",
            role="admin",
        )

        assert result["success"] is False


    def test_invalid_sql_returns_error_not_exception(self):
        result = execute_query(
            "SELECT * FROM nonexistent_table",
            role="admin",
        )

        assert result["success"] is False
        assert "error" in result


# =========================================================
# DATABASE-LEVEL RBAC
# =========================================================

class TestRBAC:

    def test_viewer_can_read_normal_column(self):
        result = execute_query(
            "SELECT name FROM employees",
            role="viewer",
        )

        assert result["success"] is True


    def test_viewer_cannot_read_salary(self):
        result = execute_query(
            "SELECT salary FROM employees",
            role="viewer",
        )

        assert result["success"] is False

        assert (
            "prohibited" in result["error"].lower()
            or "not authorized" in result["error"].lower()
        )


    def test_viewer_select_star_is_blocked(self):
        result = execute_query(
            "SELECT * FROM employees",
            role="viewer",
        )

        assert result["success"] is False


    def test_admin_can_read_salary(self):
        result = execute_query(
            "SELECT salary FROM employees",
            role="admin",
        )

        assert result["success"] is True


    def test_analyst_can_read_salary(self):
        result = execute_query(
            "SELECT salary FROM employees",
            role="analyst",
        )

        assert result["success"] is True


    def test_invalid_role_becomes_viewer(self):
        assert normalize_role(
            "unknown-role"
        ) == "viewer"

        result = execute_query(
            "SELECT salary FROM employees",
            role="unknown-role",
        )

        assert result["success"] is False


# =========================================================
# ROW LIMIT GOVERNANCE
# =========================================================

class TestRowLimit:

    def test_limit_added_when_missing(self):
        sql = enforce_row_limit(
            "SELECT name FROM employees"
        )

        assert "LIMIT 100" in sql.upper()


    def test_existing_limit_preserved(self):
        sql = enforce_row_limit(
            "SELECT name FROM employees LIMIT 5"
        )

        assert sql.upper().count("LIMIT") == 1
        assert "LIMIT 5" in sql.upper()


# =========================================================
# DEFENSE-IN-DEPTH MASKING
# =========================================================

class TestMasking:

    def test_viewer_salary_is_masked(self):
        results = [
            {
                "name": "Alice",
                "salary": 50000,
            }
        ]

        masked = mask_results(
            results,
            "viewer",
        )

        assert masked[0]["salary"] == "***"


    def test_admin_salary_is_not_masked(self):
        results = [
            {
                "name": "Alice",
                "salary": 50000,
            }
        ]

        masked = mask_results(
            results,
            "admin",
        )

        assert masked[0]["salary"] == 50000


    def test_masking_does_not_modify_original_data(self):
        results = [
            {
                "name": "Alice",
                "salary": 50000,
            }
        ]

        mask_results(
            results,
            "viewer",
        )

        assert results[0]["salary"] == 50000


# =========================================================
# SELF-CORRECTING AGENT
# =========================================================

class TestGenerateAndRun:

    def test_valid_question_returns_results_for_admin(self):
        result = generate_and_run(
            "Show me all employees",
            role="admin",
        )

        assert result["final_sql"] is not None
        assert result["results"] is not None


    def test_attempts_are_logged(self):
        result = generate_and_run(
            "Show me all employees",
            role="admin",
        )

        assert len(result["attempts"]) >= 1
        assert result["attempts"][0]["attempt"] == 1
# =========================================================
# QUERY TIMEOUT GOVERNANCE
# =========================================================

# =========================================================
# QUERY TIMEOUT GOVERNANCE
# =========================================================

class TestQueryTimeout:

    def test_expensive_query_is_interrupted(self):
        """
        Verify that SQLite interrupts an expensive
        read-only SELECT query when its execution
        time budget is exceeded.
        """

        expensive_query = """
        SELECT COUNT(*)
        FROM employees AS e1
        CROSS JOIN employees AS e2
        CROSS JOIN employees AS e3
        CROSS JOIN employees AS e4
        CROSS JOIN employees AS e5
        CROSS JOIN employees AS e6
        CROSS JOIN employees AS e7
        CROSS JOIN employees AS e8
        CROSS JOIN employees AS e9
        CROSS JOIN employees AS e10
        """

        result = execute_query(
            expensive_query,
            role="admin",
            timeout_seconds=0.001,
        )

        assert result["success"] is False
        assert result.get("error_type") == "query_timeout"
        assert "exceeded" in result["error"].lower()