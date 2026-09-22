"""Main evaluation harness runner for ShiftLink v1.0.

Usage:
    python -m eval.harness --suite dev [--categories A,B,C,D,E,F]
    python -m eval.harness --suite holdout [--categories A,B]

Output:
    eval/results/<run_id>/report.json
    eval/results/<run_id>/failures.jsonl
"""

import argparse
import json
import hashlib
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from eval.evaluators import evaluate_case, EvaluationResult, EVALUATORS
from shiftlink.agent.schemas import SCHEMA_VERSION


def wilson_ci_95(successes: int, total: int) -> tuple[float, float]:
    """
    Calculate 95% Wilson score interval for binomial proportion.

    Returns (lower_bound, upper_bound).
    """
    if total == 0:
        return (0.0, 0.0)

    p_hat = successes / total
    z = 1.96  # 95% confidence

    denom = 1 + z**2 / total
    center = (p_hat + z**2 / (2 * total)) / denom
    margin = z * math.sqrt(p_hat * (1 - p_hat) / total + z**2 / (4 * total**2)) / denom

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return (lower, upper)


def load_fixtures(suite: str) -> dict[str, list[dict]]:
    """Load all fixture files for a suite (dev or holdout)."""
    fixtures_dir = Path(__file__).parent / "fixtures" / suite

    if not fixtures_dir.exists():
        raise FileNotFoundError(f"Fixtures directory not found: {fixtures_dir}")

    fixtures = {}
    for json_file in sorted(fixtures_dir.glob("*.json")):
        category = json_file.stem.split("_")[1]  # e.g., "category_a_safety.json" -> "a"
        with open(json_file, encoding="utf-8") as f:
            fixtures[category.upper()] = json.load(f)

    return fixtures


def get_fixture_sha256(suite: str) -> str:
    """Compute SHA256 hash of all fixture files in a suite."""
    fixtures_dir = Path(__file__).parent / "fixtures" / suite
    hasher = hashlib.sha256()

    for json_file in sorted(fixtures_dir.glob("*.json")):
        with open(json_file, "rb", encoding=None) as f:
            hasher.update(f.read())

    return hasher.hexdigest()


def get_git_rev() -> str:
    """Get current git commit hash."""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def run_suite(
    suite: str,
    categories: Optional[list[str]] = None,
    run_id: Optional[str] = None
) -> None:
    """
    Run evaluation suite and produce report.json and failures.jsonl.

    Args:
        suite: "dev" or "holdout"
        categories: List of categories to run (default: all A-F)
        run_id: Custom run ID (default: timestamp)
    """

    if suite not in ("dev", "holdout"):
        raise ValueError("suite must be 'dev' or 'holdout'")

    if categories is None:
        categories = list(EVALUATORS.keys())
    else:
        categories = [c.upper() for c in categories]

    # Create results directory
    if run_id is None:
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")

    results_dir = Path(__file__).parent / "results" / run_id
    results_dir.mkdir(parents=True, exist_ok=True)

    # Load fixtures
    print(f"Loading {suite} fixtures...")
    fixtures = load_fixtures(suite)

    # Run evaluation
    print(f"Running categories: {', '.join(categories)}")

    category_results = {}
    failures = []

    for category in categories:
        if category not in fixtures:
            print(f"⚠ Category {category} not found in fixtures")
            continue

        cases = fixtures[category]
        successes = 0
        not_implemented = 0
        results_list = []

        for case in cases:
            expected = case.get("expected", {})
            result = evaluate_case(case, expected, category)
            results_list.append(result)

            if result.failure_type == "not_implemented":
                not_implemented += 1
            elif result.passed:
                successes += 1
            else:
                failures.append({
                    "case_id": result.case_id,
                    "category": result.category,
                    "expected": expected,
                    "actual": result.reason,
                    "failure_type": result.failure_type,
                    "case_type": case.get("type", "unknown")
                })

        total_cases = len(cases)
        evaluated_cases = total_cases - not_implemented

        # Compute metrics
        if evaluated_cases > 0:
            ratio = successes / evaluated_cases
            lower, upper = wilson_ci_95(successes, evaluated_cases)
        else:
            ratio = 0.0
            lower, upper = (0.0, 0.0)

        # Determine pass/fail based on category thresholds
        passed = False
        if category in ("B", "C", "D", "E"):  # Mandatory 100%
            passed = (evaluated_cases > 0 and successes == evaluated_cases)
        elif category in ("A", "F"):  # Proportional 95%
            passed = (evaluated_cases > 0 and ratio >= 0.95)

        category_results[category] = {
            "metric_name": _get_metric_name(category),
            "target": _get_target_threshold(category),
            "success": successes,
            "total": total_cases,
            "evaluated": evaluated_cases,
            "not_implemented": not_implemented,
            "ratio": round(ratio, 4),
            "wilson_ci_lower": round(lower, 4),
            "wilson_ci_upper": round(upper, 4),
            "passed": passed,
            "sample_breakdown": _get_sample_breakdown(results_list)
        }
        if category == "F":
            metric_summary = {}
            for name in ("precision_at_k", "recall_at_k", "unexpected_card_rate", "safety_missing_rate"):
                values = [r.metrics[name] for r in results_list if r.metrics.get(name) is not None]
                metric_summary[name] = {
                    "mean": sum(values) / len(values) if values else None,
                    "samples": len(values),
                }
            latencies = sorted(r.metrics["latency_ms"] for r in results_list
                               if r.metrics.get("latency_ms") is not None)
            metric_summary["stub_pipeline_latency_ms"] = {
                "p95": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
                "samples": len(latencies),
                "scope": "Local deterministic stub; excludes real LLM/network latency",
            }
            category_results[category]["metrics"] = metric_summary

        # Print category summary
        status = "PASS" if passed else "FAIL"
        print(f"{status} Category {category}: {successes}/{evaluated_cases} passed "
              f"({ratio*100:.1f}%, CI=[{lower*100:.1f}%, {upper*100:.1f}%])")
        if not_implemented > 0:
            print(f"  {not_implemented} cases not_implemented (module unavailable)")

    # Write report.json
    report = {
        "run_id": run_id,
        "git_rev": get_git_rev(),
        "schema_version": SCHEMA_VERSION,
        "fixture_sha256": get_fixture_sha256(suite),
        "timestamp": datetime.now().isoformat(),
        "suite": suite,
        "categories": category_results
    }

    report_path = results_dir / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport: {report_path}")

    # Write failures.jsonl
    failures_path = results_dir / "failures.jsonl"
    with open(failures_path, "w", encoding="utf-8") as f:
        for failure in failures:
            f.write(json.dumps(failure, ensure_ascii=False) + "\n")
    print(f"Failures: {failures_path}")

    # Print summary
    total_passed = sum(1 for r in category_results.values() if r["passed"])
    total_categories = len(category_results)
    print(f"\n{'='*60}")
    print(f"SUITE: {suite.upper()} | {total_passed}/{total_categories} PASS")
    print(f"{'='*60}")


def _get_metric_name(category: str) -> str:
    """Get human-readable metric name for category."""
    names = {
        "A": "Safety Card Retrieval Accuracy",
        "B": "Handover Method Schema Compliance",
        "C": "Resolution Steps Schema Compliance",
        "D": "Restart Type & Attempt Consistency",
        "E": "v0.9 Conversion Success Rate",
        "F": "E2E Integration (ranked retrieval, unwanted cards, safety, canary)"
    }
    return names.get(category, f"Category {category}")


def _get_target_threshold(category: str) -> str:
    """Get target threshold for category."""
    if category in ("B", "C", "D", "E"):
        return "100%"
    elif category in ("A", "F"):
        return "95%"
    return "N/A"


def _get_sample_breakdown(results: list[EvaluationResult]) -> dict[str, int]:
    """Get breakdown of test case types (normal, error, boundary)."""
    # For now, return empty (would need case.type from results)
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="ShiftLink v1.0 Evaluation Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m eval.harness --suite dev
  python -m eval.harness --suite dev --categories A,B,C
  python -m eval.harness --suite holdout --run-id custom-001
        """
    )

    parser.add_argument(
        "--suite",
        choices=["dev", "holdout"],
        required=True,
        help="Test suite to run"
    )

    parser.add_argument(
        "--categories",
        type=lambda s: s.split(","),
        help="Categories to evaluate (comma-separated, default: all)"
    )

    parser.add_argument(
        "--run-id",
        help="Custom run ID (default: timestamp)"
    )

    args = parser.parse_args()

    try:
        run_suite(
            suite=args.suite,
            categories=args.categories,
            run_id=args.run_id
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
