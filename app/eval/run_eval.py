"""Run the LLM-backed evaluation suite and report functional correctness and latency.

Usage from repository root:
    python app/eval/run_eval.py
This uses the GROQ_API_KEY from app/.env and is not part of offline CI.
"""
import json
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from app.app.llm_service import generate_and_run


def load_test_cases(path=None):
    path = Path(path) if path else Path(__file__).resolve().parent / "evaluation_cases.json"
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def evaluate_case(case: dict) -> dict:
    started = time.perf_counter()
    result = generate_and_run(case["question"], role=case.get("role", "viewer"))
    latency_ms = round((time.perf_counter() - started) * 1000, 1)
    rows = result.get("results")
    sql = result.get("final_sql") or ""
    succeeded = result.get("error") is None and rows is not None
    passed = succeeded == bool(case.get("should_succeed", True))

    if passed and succeeded and case.get("expected_columns"):
        actual_columns = {str(key).lower() for row in rows for key in row}
        expected_columns = {str(key).lower() for key in case["expected_columns"]}
        passed = expected_columns.issubset(actual_columns)

    if passed and succeeded and case.get("expected_department"):
        expected = str(case["expected_department"]).lower()
        passed = bool(rows) and all(str(row.get("department", "")).lower() == expected for row in rows)

    if passed and succeeded and "expected_row_count" in case:
        passed = len(rows) == case["expected_row_count"]

    if passed and case.get("expected_order_by"):
        passed = "ORDER BY" in sql.upper() and case["expected_order_by"].upper() in sql.upper().split("ORDER BY", 1)[1]

    if case.get("expected_security_block"):
        passed = result.get("error_type") == "authorization_denied" and rows is None

    return {
        "id": case.get("id", "UNSPECIFIED"),
        "question": case["question"],
        "role": case.get("role", "viewer"),
        "passed": passed,
        "latency_ms": latency_ms,
        "success": succeeded,
        "error_type": result.get("error_type"),
        "sql": sql or None,
        "rows_returned": len(rows) if rows is not None else None,
        "attempts_used": len(result.get("attempts", [])),
    }


def run_evaluation():
    cases = load_test_cases()
    results = [evaluate_case(case) for case in cases]
    total = len(results)
    passed = sum(item["passed"] for item in results)
    latencies = sorted(item["latency_ms"] for item in results)
    p95_index = min(total - 1, max(0, int(0.95 * total) - 1)) if total else 0
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate_percent": round(100 * passed / total, 1) if total else 0.0,
        "median_latency_ms": latencies[len(latencies) // 2] if latencies else None,
        "p95_latency_ms_approx": latencies[p95_index] if latencies else None,
        "results": results,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    output = Path(__file__).resolve().parent / "evaluation_results.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved evaluation report to {output}")
    return summary


if __name__ == "__main__":
    run_evaluation()
