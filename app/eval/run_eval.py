import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.llm_service import generate_and_run


def load_test_cases(path="eval/test_cases.json"):
    with open(path) as f:
        return json.load(f)


def evaluate_case(case: dict) -> dict:
    question = case["question"]
    result = generate_and_run(question)

    sql = (result.get("final_sql") or "").upper()
    executed_successfully = result.get("final_sql") is not None

    if case.get("expects_failure"):
        passed = not executed_successfully
    else:
        passed = executed_successfully

        if passed and "expects_table" in case:
            passed = case["expects_table"].upper() in sql

        if passed and case.get("expects_aggregate"):
            passed = any(fn in sql for fn in ["COUNT(", "AVG(", "SUM(", "MAX(", "MIN("])

        if passed and case.get("expects_where"):
            passed = case["expects_where"].upper() in sql

        if passed and case.get("expects_order_by"):
            passed = "ORDER BY" in sql

    return {
        "question": question,
        "passed": passed,
        "sql_generated": result.get("final_sql"),
        "attempts_used": len(result.get("attempts", [])),
        "retried": len(result.get("attempts", [])) > 1,
    }


def run_evaluation():
    cases = load_test_cases()
    results = [evaluate_case(case) for case in cases]

    passed_count = sum(r["passed"] for r in results)
    total = len(results)
    retried_count = sum(r["retried"] for r in results)

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        retry_note = f" (retried, {r['attempts_used']} attempts)" if r["retried"] else ""
        print(f"[{status}] {r['question']}{retry_note}")
        print(f"       SQL: {r['sql_generated']}")

    print("=" * 60)
    print(f"Success rate: {passed_count}/{total} ({passed_count/total*100:.1f}%)")
    print(f"Queries that needed a retry: {retried_count}/{total}")
    print("=" * 60 + "\n")

    return results


if __name__ == "__main__":
    run_evaluation()