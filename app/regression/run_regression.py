import json
import os
import re
import time
from datetime import datetime, timezone

from app.app.llm_service import generate_and_run, execute_query


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CASES_PATH = os.path.join(
    BASE_DIR,
    "regression_cases.json",
)

RESULTS_PATH = os.path.join(
    BASE_DIR,
    "regression_results.json",
)


def load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def normalize_sql(sql):
    """
    Normalize SQL only for reporting/debugging.

    We do NOT rely on raw SQL string equality to decide whether
    two queries are functionally equivalent.
    """
    if not sql:
        return ""

    sql = sql.strip().rstrip(";")
    sql = re.sub(r"\s+", " ", sql)

    # Row-limit governance may automatically add LIMIT 100.
    sql = re.sub(
        r"\s+LIMIT\s+100$",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    return sql.strip().lower()


def normalize_results(results):
    """
    Convert result rows into a stable representation so
    equivalent result sets can be compared.
    """
    if results is None:
        return None

    normalized = []

    for row in results:
        normalized_row = {
            key: row[key]
            for key in sorted(row.keys())
        }

        normalized.append(normalized_row)

    normalized.sort(
        key=lambda row: json.dumps(
            row,
            sort_keys=True,
            default=str,
        )
    )

    return normalized


def compare_expected_sql(
    expected_sql,
    generated_result,
    role,
):
    """
    Compare expected and generated SQL by their actual database
    results rather than requiring identical SQL text.
    """

    expected_execution = execute_query(
        expected_sql,
        role=role,
    )

    if not expected_execution.get("success"):
        return {
            "passed": False,
            "reason": (
                "The verified expected SQL could not be executed: "
                + expected_execution.get(
                    "error",
                    "unknown error",
                )
            ),
        }

    generated_results = generated_result.get("results")

    if generated_results is None:
        return {
            "passed": False,
            "reason": (
                "Generated query did not return successful results."
            ),
        }

    expected_results = normalize_results(
        expected_execution.get("results")
    )

    actual_results = normalize_results(
        generated_results
    )

    if expected_results == actual_results:
        return {
            "passed": True,
            "reason": (
                "Generated SQL produced the same result "
                "as the verified SQL."
            ),
        }

    return {
        "passed": False,
        "reason": (
            "Generated SQL returned different results "
            "from the verified SQL."
        ),
    }


def compare_expected_behavior(
    expected_behavior,
    generated_result,
):
    """
    Validate governance/security behavior such as RBAC denial.
    """

    attempts = generated_result.get(
        "attempts",
        [],
    )

    error_type = generated_result.get(
        "error_type"
    )

    if (
        expected_behavior == "authorization_denied"
    ):
        if error_type == "authorization_denied":
            return {
                "passed": True,
                "reason": (
                    "Restricted data access was correctly denied."
                ),
            }

        for attempt in attempts:
            if (
                attempt.get("error_type")
                == "authorization_denied"
            ):
                return {
                    "passed": True,
                    "reason": (
                        "Restricted data access was correctly denied."
                    ),
                }

        return {
            "passed": False,
            "reason": (
                "Expected authorization denial, "
                "but restricted access was not blocked."
            ),
        }

    return {
        "passed": False,
        "reason": (
            f"Unknown expected behavior: {expected_behavior}"
        ),
    }


def run_case(case):
    case_id = case["id"]
    question = case["question"]
    role = case.get("role", "viewer")

    print()
    print(
        f"Running {case_id}: {question}"
    )

    start_time = time.perf_counter()

    result = generate_and_run(
        question,
        role=role,
    )

    latency = (
        time.perf_counter()
        - start_time
    )

    generated_sql = result.get(
        "final_sql"
    )

    if "expected_sql" in case:
        comparison = compare_expected_sql(
            case["expected_sql"],
            result,
            role,
        )

        expectation_type = "sql_result_equivalence"

    elif "expected_behavior" in case:
        comparison = compare_expected_behavior(
            case["expected_behavior"],
            result,
        )

        expectation_type = "governance_behavior"

    else:
        comparison = {
            "passed": False,
            "reason": (
                "Regression case has no supported expectation."
            ),
        }

        expectation_type = "invalid"

    status = (
        "PASS"
        if comparison["passed"]
        else "FAIL"
    )

    print(
        f"{status} | "
        f"Latency: {latency:.3f}s"
    )

    if not comparison["passed"]:
        print(
            "Reason:",
            comparison["reason"],
        )

    return {
        "id": case_id,
        "description": case.get(
            "description",
            "",
        ),
        "question": question,
        "role": role,
        "expectation_type": expectation_type,
        "expected_sql": case.get(
            "expected_sql"
        ),
        "expected_behavior": case.get(
            "expected_behavior"
        ),
        "generated_sql": generated_sql,
        "normalized_generated_sql": normalize_sql(
            generated_sql
        ),
        "passed": comparison["passed"],
        "reason": comparison["reason"],
        "latency_seconds": round(
            latency,
            3,
        ),
        "confidence": result.get(
            "confidence"
        ),
        "error": result.get(
            "error"
        ),
        "error_type": result.get(
            "error_type"
        ),
        "attempts": result.get(
            "attempts",
            [],
        ),
    }


def run_regression_suite():
    cases = load_cases()

    print("=" * 70)
    print("QUERYMIND REGRESSION TEST SUITE")
    print("=" * 70)

    results = []

    for case in cases:
        results.append(
            run_case(case)
        )

    passed_count = sum(
        1
        for result in results
        if result["passed"]
    )

    total_count = len(results)

    failed_count = (
        total_count
        - passed_count
    )

    pass_rate = (
        (passed_count / total_count) * 100
        if total_count
        else 0
    )

    report = {
        "generated_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "summary": {
            "total": total_count,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round(
                pass_rate,
                2,
            ),
        },
        "results": results,
    }

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            indent=2,
            default=str,
        )

    print()
    print("=" * 70)
    print("REGRESSION SUMMARY")
    print("=" * 70)

    print(
        f"Passed: {passed_count}/{total_count}"
    )

    print(
        f"Failed: {failed_count}/{total_count}"
    )

    print(
        f"Pass rate: {pass_rate:.2f}%"
    )

    print(
        f"Results saved to: {RESULTS_PATH}"
    )

    return report


if __name__ == "__main__":
    run_regression_suite()