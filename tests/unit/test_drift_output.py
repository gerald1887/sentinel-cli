"""Unit tests for Drift drift output rendering."""

from __future__ import annotations

from sentinel.drift.comparator import MetricComparisonResult
from sentinel.drift.output import render_drift_baseline, render_drift_check
from sentinel.drift.runner import (
    DriftBaselineRunResult,
    DriftBaselineSummary,
    DriftCheckRunResult,
    DriftCheckSummary,
)
from sentinel.drift.threshold_engine import ThresholdEvaluationResult
from sentinel.drift.types import MetricFamily, MetricResultRecord


def test_render_drift_baseline_summary_only() -> None:
    result = DriftBaselineRunResult(
        status="PASS",
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        baseline_path="baseline.json",
        summary=DriftBaselineSummary(
            total_cases=3,
            executed_cases=3,
            approved_cases=3,
            error_cases=0,
            metrics=7,
        ),
        metrics=[],
    )
    assert render_drift_baseline(result) == [
        "DRIFT BASELINE SUMMARY total_cases=3 approved=3 errors=0 metrics=7"
    ]


def test_render_drift_check_summary_first_and_only_fail_error_lines() -> None:
    result = DriftCheckRunResult(
        status="FAIL",
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
        summary=DriftCheckSummary(total_findings=3, passed=1, failed=1, errors=1, total_cases=3, approved_cases=2),
        comparisons=[
            MetricComparisonResult(
                status="PASS",
                family=MetricFamily.PRESENCE,
                path="/b",
                metric_id="m2",
                key="presence_rate",
                baseline_value=0.8,
                current_value=0.5,
                delta=-0.3,
                is_rate_metric=True,
            )
        ],
        evaluations=[
            ThresholdEvaluationResult(
                status="PASS",
                family=MetricFamily.NUMERIC,
                path="/a",
                metric_id="m1",
                key="mean",
                rule_source="metric-family",
                rule_form="max_abs_delta",
                message="ok",
            ),
            ThresholdEvaluationResult(
                status="FAIL",
                family=MetricFamily.PRESENCE,
                path="/b",
                metric_id="m2",
                key="presence_rate",
                rule_source="per-key",
                rule_form="max_rate_delta",
                message="Threshold check failed.",
                details={"max_rate_delta": 0.1},
            ),
            ThresholdEvaluationResult(
                status="ERROR",
                family=MetricFamily.COVERAGE,
                path="/c",
                metric_id="m3",
                key=None,
                rule_source="none",
                rule_form=None,
                message="Comparator produced error result.",
            ),
        ],
        current_metrics=[
            MetricResultRecord(metric_id="m_cov", family=MetricFamily.COVERAGE, path="/coverage", key="total_cases", value=3.0),  # noqa: E501
            MetricResultRecord(metric_id="m_cov", family=MetricFamily.COVERAGE, path="/coverage", key="approved_cases", value=2.0),  # noqa: E501
        ],
    )
    assert render_drift_check(result) == [
        "DRIFT SUMMARY total_metrics=3 pass=1 fail=1 error=1 cases=3 approved=2",
        "METRIC FAIL presence /b m2.presence_rate baseline=0.8 current=0.5 delta=-0.3 threshold=0.1",
        "METRIC ERROR coverage /c m3 Comparator produced error result.",
    ]
