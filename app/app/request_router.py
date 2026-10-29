
import re

ANALYTICS_TERMS = {
    "sales", "revenue", "profit", "order", "orders",
    "customer", "customers", "employee", "employees",
    "department", "departments", "product", "products",
    "region", "regions", "salary", "salaries",
    "database", "table", "records", "record", "data",
    "average", "total", "count", "trend", "trends",
    "compare", "comparison", "highest", "lowest",
    "increase", "decrease", "decline", "performance",
    "monthly", "weekly", "yearly", "quarterly",
}

ANALYTICS_PHRASES = (
    "show me", "how many", "how much", "break down",
    "group by", "top ", "bottom ", "why did",
    "what caused", "compare ", "calculate ",
    "summarize ", "analyse ", "analyze ", "which ", "list ",
)


def classify_request(question: str) -> dict:
    """Classify whether a request appears to concern business data."""

    if not isinstance(question, str) or not question.strip():
        return {
            "allowed": False,
            "category": "invalid",
            "reason": "Please enter a business-data question.",
        }

    normalized = re.sub(r"\s+", " ", question.lower()).strip()
    words = set(re.findall(r"[a-z]+", normalized))

    if words.intersection(ANALYTICS_TERMS):
        return {
            "allowed": True,
            "category": "business_analytics",
            "reason": "The question appears to concern business data.",
        }

    if any(phrase in normalized for phrase in ANALYTICS_PHRASES):
        return {
            "allowed": True,
            "category": "business_analytics",
            "reason": "The question appears to request data analysis.",
        }

    return {
        "allowed": False,
        "category": "out_of_scope",
        "reason": (
            "QueryMind handles questions about available business "
            "data, such as sales, customers, orders, and employees."
        ),
    }
