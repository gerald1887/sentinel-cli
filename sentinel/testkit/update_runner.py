"""Regression update-suite orchestrator (snapshot writer)."""

from __future__ import annotations

from sentinel.core.errors import INTERNAL_ERROR, SentinelError
from sentinel.testkit.case_executor import execute_case
from sentinel.testkit.snapshots import resolve_snapshot_path, write_snapshot
from sentinel.testkit.suite_loader import load_suite
from sentinel.testkit.types import UpdateCaseResult, UpdateSuiteResult, UpdateSummary


def _error_text(err: SentinelError) -> str:
    return f"{err.category}|{err.code}|{err.message}"


def _internal_error(case_id: str, code: str, message: str) -> SentinelError:
    return SentinelError(
        category=INTERNAL_ERROR,
        code=code,
        message=message,
        details={"case_id": case_id},
    )


def run_update(suite_path: str) -> UpdateSuiteResult | SentinelError:
    """Update snapshots for all cases in a suite."""
    suite = load_suite(suite_path)
    if isinstance(suite, SentinelError):
        return suite

    case_results: list[UpdateCaseResult] = []

    for case in suite.cases:
        approved_output = execute_case(case)
        if isinstance(approved_output, SentinelError):
            case_results.append(
                UpdateCaseResult(
                    case_id=case.case_id,
                    status="ERROR",
                    errors=[_error_text(approved_output)],
                )
            )
            continue

        try:
            snapshot_path = resolve_snapshot_path(suite.suite_path, case.case_id)
        except Exception:  # noqa: BLE001
            err = _internal_error(
                case.case_id,
                code="SENTINEL_UPDATE_SNAPSHOT_PATH_ERROR",
                message="Snapshot path resolution failed.",
            )
            case_results.append(
                UpdateCaseResult(
                    case_id=case.case_id,
                    status="ERROR",
                    errors=[_error_text(err)],
                )
            )
            continue

        try:
            write_err = write_snapshot(snapshot_path, approved_output)
        except Exception:  # noqa: BLE001
            err = _internal_error(
                case.case_id,
                code="SENTINEL_UPDATE_SNAPSHOT_WRITE_ERROR",
                message="Snapshot write raised unexpectedly.",
            )
            case_results.append(
                UpdateCaseResult(
                    case_id=case.case_id,
                    status="ERROR",
                    errors=[_error_text(err)],
                )
            )
            continue

        if isinstance(write_err, SentinelError):
            case_results.append(
                UpdateCaseResult(
                    case_id=case.case_id,
                    status="ERROR",
                    errors=[_error_text(write_err)],
                )
            )
            continue

        case_results.append(UpdateCaseResult(case_id=case.case_id, status="UPDATED"))

    summary = UpdateSummary(
        total=len(case_results),
        updated=sum(1 for c in case_results if c.status == "UPDATED"),
        errors=sum(1 for c in case_results if c.status == "ERROR"),
    )

    return UpdateSuiteResult(
        command="update",
        suite_path=suite.suite_path,
        summary=summary,
        cases=case_results,
    )

