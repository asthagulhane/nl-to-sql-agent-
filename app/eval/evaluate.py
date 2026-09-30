import json
import os
import time

from app.app.llm_service import generate_and_run
from app.app.semantic_layer import get_matching_definitions


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CASES_PATH = os.path.join(
    BASE_DIR,
    "evaluation_cases.json",
)

RESULTS_PATH = os.path.join(
    BASE_DIR,
    "evaluation_results.json",
)


def load_cases():
    with open(CASES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def evaluate_case(case):
    start_time = time.perf_counter()

    result = generate_and_run(
        case["question"],
        role=case.get("role", "viewer"),
    )

    latency_seconds = round(
        time.perf_counter() - start_time,
        3,
    )

    generated_sql = result.get("final_sql")
    rows = result.get("results")
    error = result.get("error")

    actual_success = (
        generated_sql is not None
        and rows is not None
    )

    checks = {}

    # ---------------------------------------------
    # Success / failure expectation
    # ---------------------------------------------

    checks["success_behavior"] = (
        actual_success
        == case["should_succeed"]
    )

    # ---------------------------------------------
    # Expected columns
    # ---------------------------------------------

    expected_columns = case.get(
        "expected_columns"
    )

    if expected_columns and rows:
        actual_columns = set(rows[0].keys())

        checks["expected_columns"] = (
            set(expected_columns)
            .issubset(actual_columns)
        )

    # ---------------------------------------------
    # Department correctness
    # ---------------------------------------------

    expected_department = case.get(
        "expected_department"
    )

    if expected_department and rows:
        checks["department_filter"] = all(
            row.get("department")
            == expected_department
            for row in rows
        )

    # ---------------------------------------------
    # Security / RBAC behavior
    # ---------------------------------------------

    if case.get("expected_security_block"):
        checks["security_block"] = (
            not actual_success
        )

    # ---------------------------------------------
    # Semantic-layer behavior
    # ---------------------------------------------

    semantic_term = case.get(
        "semantic_term"
    )

    matched_definitions = (
        get_matching_definitions(
            case["question"]
        )
    )

    matched_terms = [
        definition["term"]
        for definition in matched_definitions
    ]

    if semantic_term:
        checks["semantic_definition"] = (
            semantic_term in matched_terms
        )

    passed = (
        all(checks.values())
        if checks
        else False
    )

    return {
        "id": case["id"],
        "question": case["question"],
        "role": case.get("role", "viewer"),
        "passed": passed,
        "checks": checks,
        "generated_sql": generated_sql,
        "confidence": result.get(
            "confidence"
        ),
        "latency_seconds": latency_seconds,
        "row_count": (
            len(rows)
            if rows is not None
            else 0
        ),
        "semantic_terms": matched_terms,
        "error": error,
    }


def main():
    cases = load_cases()

    results = []

    print("=" * 70)
    print("QUERYMIND EVALUATION")
    print("=" * 70)

    for case in cases:
        print(
            f"\nRunning {case['id']}: "
            f"{case['question']}"
        )

        result = evaluate_case(case)

        results.append(result)

        status = (
            "PASS"
            if result["passed"]
            else "FAIL"
        )

        print(
            f"{status} | "
            f"Latency: "
            f"{result['latency_seconds']}s"
        )

    passed_count = sum(
        result["passed"]
        for result in results
    )

    total_count = len(results)

    accuracy = (
        passed_count / total_count * 100
        if total_count
        else 0
    )

    summary = {
        "total_cases": total_count,
        "passed": passed_count,
        "failed": (
            total_count - passed_count
        ),
        "accuracy_percent": round(
            accuracy,
            2,
        ),
        "results": results,
    }

    with open(
        RESULTS_PATH,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
        )

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print(
        f"Passed: {passed_count}/"
        f"{total_count}"
    )

    print(
        f"Accuracy: "
        f"{accuracy:.2f}%"
    )

    print(
        f"Results saved to: "
        f"{RESULTS_PATH}"
    )


if __name__ == "__main__":
    main()