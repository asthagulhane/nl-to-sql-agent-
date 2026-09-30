from app.app.semantic_layer import (
    get_matching_definitions,
    build_semantic_context,
)


class TestSemanticLayer:

    def test_active_employee_definition_matches(self):
        matches = get_matching_definitions(
            "Show me all active employee records"
        )

        assert len(matches) == 1
        assert matches[0]["term"] == "active employee"
        assert matches[0]["sql_rule"] == "employees.status = 'active'"

    def test_engineering_employee_definition_matches(self):
        matches = get_matching_definitions(
            "Show me engineering employee records"
        )

        assert len(matches) == 1
        assert matches[0]["term"] == "engineering employee"
        assert (
            matches[0]["sql_rule"]
            == "employees.department = 'Engineering'"
        )

    def test_high_salary_employee_definition_matches(self):
        matches = get_matching_definitions(
            "Show me every high salary employee"
        )

        assert len(matches) == 1
        assert matches[0]["term"] == "high salary employee"
        assert matches[0]["sql_rule"] == "employees.salary > 100000"

    def test_unrelated_question_returns_no_definition(self):
        matches = get_matching_definitions(
            "Show me every department"
        )

        assert matches == []

    def test_matching_is_case_insensitive(self):
        matches = get_matching_definitions(
            "SHOW ME ACTIVE EMPLOYEE RECORDS"
        )

        assert len(matches) == 1
        assert matches[0]["term"] == "active employee"

    def test_semantic_context_contains_approved_rule(self):
        context = build_semantic_context(
            "Show me engineering employee records"
        )

        assert "Approved business definitions" in context
        assert "engineering employee" in context
        assert "employees.department = 'Engineering'" in context

    def test_semantic_context_empty_when_no_match(self):
        context = build_semantic_context(
            "Show me every department"
        )

        assert context == ""