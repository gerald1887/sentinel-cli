"""Regression run-suite orchestrator."""

from __future__ import annotations

from sentinel.core.errors import SentinelError
from sentinel.testkit.case_executor import execute_case
from sentinel.testkit.comparator import compare_json
from sentinel.testkit.snapshots import read_snapshot, resolve_snapshot_path
from sentinel.testkit.suite_loader import load_suite
from sentinel.testkit.types import RunCaseResult, RunSuiteResult, RunSummary


def _error_text(err: SentinelError) -> str:
    return f"{err.category}|{err.code}|{err.message}"


def run_suite(suite_path: str) -> RunSuiteResult | SentinelError:
    """Run Regression suite flow (load -> execute -> snapshot read -> compare)."""
    suite = load_suite(suite_path)
    if isinstance(suite, SentinelError):
        return suite

    case_results: list[RunCaseResult] = []

    for case in suite.cases:
        approved_output = execute_case(case)
        if isinstance(approved_output, SentinelError):
            case_results.append(
                RunCaseResult(
                    case_id=case.case_id,
                    status="ERROR",
                    errors=[_error_text(approved_output)],
                )
            )
            continue

        snapshot_path = resolve_snapshot_path(suite.suite_path, case.case_id)
        expected_snapshot = read_snapshot(snapshot_path)
        if isinstance(expected_snapshot, SentinelError):
            case_results.append(
                RunCaseResult(
                    case_id=case.case_id,
                    status="ERROR",
                    errors=[_error_text(expected_snapshot)],
                )
            )
            continue

        diffs = compare_json(
            expected_snapshot, approved_output, ignore_paths=case.ignore_paths
        )
        if diffs:
            case_results.append(
                RunCaseResult(case_id=case.case_id, status="DIFF", diffs=diffs)
            )
        else:
            case_results.append(RunCaseResult(case_id=case.case_id, status="PASS"))

    summary = RunSummary(
        total=len(case_results),
        pass_count=sum(1 for c in case_results if c.status == "PASS"),
        diff_count=sum(1 for c in case_results if c.status == "DIFF"),
        error_count=sum(1 for c in case_results if c.status == "ERROR"),
    )

    return RunSuiteResult(
        command="run",
        suite_path=suite.suite_path,
        summary=summary,
        cases=case_results,
    )

