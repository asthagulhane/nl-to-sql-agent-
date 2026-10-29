
from app.request_router import classify_request


def test_business_revenue_question_is_allowed():
    result = classify_request("Why did revenue decline last month?")
    assert result["allowed"] is True
    assert result["category"] == "business_analytics"


def test_sales_comparison_is_allowed():
    result = classify_request("Compare sales across regions")
    assert result["allowed"] is True


def test_salary_question_is_routed_to_governance():
    # Routing does not grant permission to read salary data.
    result = classify_request("Show employee salaries")
    assert result["allowed"] is True


def test_unrelated_poem_is_rejected():
    result = classify_request("Write a poem about the moon")
    assert result["allowed"] is False
    assert result["category"] == "out_of_scope"


def test_empty_question_is_rejected():
    result = classify_request("   ")
    assert result["allowed"] is False
    assert result["category"] == "invalid"
