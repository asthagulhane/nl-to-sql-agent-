
import sqlite3

from app.llm_service import (
    execute_query,
    validate_sql_candidate,
)


def create_test_database(tmp_path):
    db_path = tmp_path / "security_test.db"

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT,
            salary INTEGER
        )
        """
    )

    connection.execute(
        """
        INSERT INTO employees (name, salary)
        VALUES ('Alice', 90000)
        """
    )

    connection.commit()
    connection.close()

    return str(db_path)


def test_select_query_is_allowed(tmp_path):
    db_path = create_test_database(tmp_path)

    result = execute_query(
        "SELECT name FROM employees",
        db_path=db_path,
        role="viewer",
    )

    assert result["success"] is True
    assert result["results"][0]["name"] == "Alice"


def test_insert_is_rejected(tmp_path):
    db_path = create_test_database(tmp_path)

    result = execute_query(
        "INSERT INTO employees (name, salary) VALUES ('Bob', 80000)",
        db_path=db_path,
        role="admin",
    )

    assert result["success"] is False
    assert result["error_type"] == "query_not_allowed"


def test_update_is_rejected(tmp_path):
    db_path = create_test_database(tmp_path)

    result = execute_query(
        "UPDATE employees SET salary = 1",
        db_path=db_path,
        role="admin",
    )

    assert result["success"] is False
    assert result["error_type"] == "query_not_allowed"


def test_delete_is_rejected(tmp_path):
    db_path = create_test_database(tmp_path)

    result = execute_query(
        "DELETE FROM employees",
        db_path=db_path,
        role="admin",
    )

    assert result["success"] is False
    assert result["error_type"] == "query_not_allowed"


def test_multiple_statements_are_rejected():
    valid, _ = validate_sql_candidate(
        "SELECT name FROM employees; DELETE FROM employees"
    )

    assert valid is False


def test_viewer_cannot_read_salary(tmp_path):
    db_path = create_test_database(tmp_path)

    result = execute_query(
        "SELECT salary FROM employees",
        db_path=db_path,
        role="viewer",
    )

    assert result["success"] is False
    assert result["error_type"] == "authorization_denied"


def test_query_results_are_bounded(tmp_path):
    db_path = create_test_database(tmp_path)

    result = execute_query(
        "SELECT id, name FROM employees",
        db_path=db_path,
        role="viewer",
    )

    assert result["success"] is True
    assert result["row_count"] <= 100


def test_existing_large_limit_cannot_bypass_result_cap(tmp_path):
    db_path = create_test_database(tmp_path)
    connection = sqlite3.connect(db_path)
    connection.executemany(
        "INSERT INTO employees (name, salary) VALUES (?, ?)",
        [(f"Employee {i}", 50000 + i) for i in range(150)],
    )
    connection.commit()
    connection.close()

    result = execute_query(
        "SELECT id, name FROM employees LIMIT 100000",
        db_path=db_path,
        role="viewer",
    )

    assert result["success"] is True
    assert result["row_count"] == 100
    assert len(result["results"]) == 100
    assert result["truncated"] is True


def test_ordered_query_is_bounded_without_losing_order(tmp_path):
    db_path = create_test_database(tmp_path)
    connection = sqlite3.connect(db_path)
    connection.executemany(
        "INSERT INTO employees (name, salary) VALUES (?, ?)",
        [(f"Employee {i:03d}", 50000 + i) for i in range(150)],
    )
    connection.commit()
    connection.close()

    result = execute_query(
        "SELECT id, name FROM employees ORDER BY name DESC LIMIT 100000;",
        db_path=db_path,
        role="viewer",
    )

    assert result["success"] is True
    assert result["row_count"] == 100
    assert result["truncated"] is True
    assert result["results"][0]["name"] == "Employee 149"
