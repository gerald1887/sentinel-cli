"""Drift drift orchestration runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.drift.baseline_store import read_baseline, write_baseline
from sentinel.drift.comparator import MetricComparisonResult, compare_metrics
from sentinel.drift.config_loader import load_metrics_config, load_thresholds_config
from sentinel.drift.metric_engine import SuiteCoverageSummary, compute_metrics
from sentinel.drift.threshold_engine import (
    ThresholdConfig,
    ThresholdEvaluationResult,
    evaluate_thresholds,
)
from sentinel.drift.types import BASELINE_VERSION, BaselineEnvelope, MetricResultRecord
from sentinel.testkit.case_executor import execute_case
from sentinel.testkit.suite_loader import load_suite


@dataclass(frozen=True, slots=True)
class DriftBaselineSummary:
    total_cases: int
    executed_cases: int
    approved_cases: int
    error_cases: int
    metrics: int


@dataclass(frozen=True, slots=True)
class DriftBaselineRunResult:
    status: Literal["PASS", "ERROR"]
    suite_path: str
    metrics_config_path: str
    baseline_path: str
    summary: DriftBaselineSummary
    metrics: list[MetricResultRecord]


@dataclass(frozen=True, slots=True)
class DriftCheckSummary:
    total_findings: int
    passed: int
    failed: int
    errors: int
    total_cases: int
    approved_cases: int


@dataclass(frozen=True, slots=True)
class DriftCheckRunResult:
    status: Literal["PASS", "FAIL", "ERROR"]
    suite_path: str
    metrics_config_path: str
    thresholds_config_path: str
    baseline_path: str
    summary: DriftCheckSummary
    comparisons: list[MetricComparisonResult]
    evaluations: list[ThresholdEvaluationResult]
    current_metrics: list[MetricResultRecord]


def _drift_error(code: str, message: str, details: dict[str, object] | None = None) -> SentinelError:
    return SentinelError(category=SCHEMA_INVALID, code=code, message=message, details=details)


def _execute_suite_outputs(
    suite_path: str,
) -> tuple[list[object], SuiteCoverageSummary, SentinelError | None]:
    suite = load_suite(suite_path)
    if isinstance(suite, SentinelError):
        return [], SuiteCoverageSummary(total_cases=0, executed_cases=0, approved_cases=0, error_cases=0), suite

    approved_outputs: list[object] = []
    error_cases = 0
    executed_cases = 0

    for case in suite.cases:
        executed_cases += 1
        approved_output = execute_case(case)
        if isinstance(approved_output, SentinelError):
            error_cases += 1
            continue
        approved_outputs.append(approved_output)

    summary = SuiteCoverageSummary(
        total_cases=len(suite.cases),
        executed_cases=executed_cases,
        approved_cases=len(approved_outputs),
        error_cases=error_cases,
    )
    if error_cases > 0:
        return approved_outputs, summary, _drift_error(
            code="SENTINEL_DRIFT_SUITE_EXECUTION_ERROR",
            message="Suite execution produced one or more case errors.",
            details={
                "suite_path": suite_path,
                "total_cases": len(suite.cases),
                "approved_cases": len(approved_outputs),
                "error_cases": error_cases,
            },
        )
    return approved_outputs, summary, None


def run_drift_baseline(
    *,
    suite_path: str,
    metrics_config_path: str,
    baseline_path: str,
    assertion_outcomes: list[str] | None = None,
) -> DriftBaselineRunResult | SentinelError:
    """Run drift baseline orchestration flow."""
    metrics_config = load_metrics_config(metrics_config_path)
    if isinstance(metrics_config, SentinelError):
        return metrics_config

    approved_outputs, coverage_summary, suite_error = _execute_suite_outputs(suite_path)
    if suite_error is not None:
        return suite_error

    computed_metrics = compute_metrics(
        metrics_config,
        approved_outputs=approved_outputs,
        assertion_outcomes=assertion_outcomes,
        suite_coverage_summary=coverage_summary,
    )
    if isinstance(computed_metrics, SentinelError):
        return computed_metrics

    baseline = BaselineEnvelope(
        version=BASELINE_VERSION,
        suite=suite_path,
        metrics=computed_metrics,
    )
    write_error = write_baseline(baseline_path, baseline)
    if isinstance(write_error, SentinelError):
        return write_error

    return DriftBaselineRunResult(
        status="PASS",
        suite_path=suite_path,
        metrics_config_path=metrics_config_path,
        baseline_path=baseline_path,
        summary=DriftBaselineSummary(
            total_cases=coverage_summary.total_cases,
            executed_cases=coverage_summary.executed_cases,
            approved_cases=coverage_summary.approved_cases,
            error_cases=coverage_summary.error_cases,
            metrics=len(computed_metrics),
        ),
        metrics=computed_metrics,
    )


def run_drift_check(
    *,
    suite_path: str,
    metrics_config_path: str,
    thresholds_config_path: str,
    baseline_path: str,
    assertion_outcomes: list[str] | None = None,
) -> DriftCheckRunResult | SentinelError:
    """Run drift check orchestration flow."""
    metrics_config = load_metrics_config(metrics_config_path)
    if isinstance(metrics_config, SentinelError):
        return metrics_config

    thresholds_config = load_thresholds_config(thresholds_config_path)
    if isinstance(thresholds_config, SentinelError):
        return thresholds_config
    if not isinstance(thresholds_config, ThresholdConfig):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_RUNTIME_TYPE",
            message="Threshold config must already be in locked threshold-engine form.",
            details={"thresholds_config_path": thresholds_config_path},
        )

    baseline = read_baseline(baseline_path)
    if isinstance(baseline, SentinelError):
        return baseline

    approved_outputs, coverage_summary, suite_error = _execute_suite_outputs(suite_path)
    if suite_error is not None:
        return suite_error

    current_metrics = compute_metrics(
        metrics_config,
        approved_outputs=approved_outputs,
        assertion_outcomes=assertion_outcomes,
        suite_coverage_summary=coverage_summary,
    )
    if isinstance(current_metrics, SentinelError):
        return current_metrics

    comparison_output = compare_metrics(baseline.metrics, current_metrics)
    evaluations = evaluate_thresholds(comparison_output, thresholds_config)

    errors = sum(1 for item in evaluations if item.status == "ERROR")
    failed = sum(1 for item in evaluations if item.status == "FAIL")
    passed = sum(1 for item in evaluations if item.status == "PASS")
    if errors > 0:
        status: Literal["PASS", "FAIL", "ERROR"] = "ERROR"
    elif failed > 0:
        status = "FAIL"
    else:
        status = "PASS"

    return DriftCheckRunResult(
        status=status,
        suite_path=suite_path,
        metrics_config_path=metrics_config_path,
        thresholds_config_path=thresholds_config_path,
        baseline_path=baseline_path,
        summary=DriftCheckSummary(
            total_findings=len(evaluations),
            passed=passed,
            failed=failed,
            errors=errors,
            total_cases=coverage_summary.total_cases,
            approved_cases=coverage_summary.approved_cases,
        ),
        comparisons=comparison_output.metric_results,
        evaluations=evaluations,
        current_metrics=current_metrics,
    )
