"""Unit tests for Drift drift CLI wiring."""

from __future__ import annotations

import sys
import types

import pytest

from sentinel.cli import main
from sentinel.core.errors import SentinelError
from sentinel.drift.runner import (
    DriftBaselineRunResult,
    DriftBaselineSummary,
    DriftCheckRunResult,
    DriftCheckSummary,
)
from sentinel.drift.threshold_engine import ThresholdEvaluationResult
from sentinel.drift.types import MetricFamily


def _install_fake_drift_runner(
    monkeypatch: pytest.MonkeyPatch,
    run_drift_baseline_impl,
    run_drift_check_impl,
) -> None:
    fake_module = types.SimpleNamespace(
        run_drift_baseline=run_drift_baseline_impl,
        run_drift_check=run_drift_check_impl,
    )
    monkeypatch.setitem(sys.modules, "sentinel.drift.runner", fake_module)


def test_drift_baseline_requires_flags() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["drift", "baseline", "--suite", "suite.yaml"])
    assert exc_info.value.code != 0


def test_drift_check_requires_flags() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["drift", "check", "--suite", "suite.yaml", "--metrics", "metrics.yaml"])
    assert exc_info.value.code != 0


def test_drift_baseline_success_prints_summary_only_exit_0(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_drift_runner(
        monkeypatch,
        lambda **_: DriftBaselineRunResult(
            status="PASS",
            suite_path="suite.yaml",
            metrics_config_path="metrics.yaml",
            baseline_path="baseline.json",
            summary=DriftBaselineSummary(
                total_cases=2,
                executed_cases=2,
                approved_cases=2,
                error_cases=0,
                metrics=5,
            ),
            metrics=[],
        ),
        lambda **_: None,
    )
    exit_code = main(
        [
            "drift",
            "baseline",
            "--suite",
            "suite.yaml",
            "--metrics",
            "metrics.yaml",
            "--output",
            "baseline.json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == (
        "DRIFT BASELINE SUMMARY total_cases=2 approved=2 errors=0 metrics=5\n"
    )


def test_drift_baseline_error_exit_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_drift_runner(
        monkeypatch,
        lambda **_: SentinelError(category="SCHEMA_INVALID", code="SENTINEL_X", message="bad"),
        lambda **_: None,
    )
    exit_code = main(
        [
            "drift",
            "baseline",
            "--suite",
            "suite.yaml",
            "--metrics",
            "metrics.yaml",
            "--output",
            "baseline.json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == "DRIFT BASELINE ERROR\nSCHEMA_INVALID SENTINEL_X bad\n"


def test_drift_check_pass_exit_0_summary_only(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_drift_runner(
        monkeypatch,
        lambda **_: None,
        lambda **_: DriftCheckRunResult(
            status="PASS",
            suite_path="suite.yaml",
            metrics_config_path="metrics.yaml",
            thresholds_config_path="thresholds.yaml",
            baseline_path="baseline.json",
            summary=DriftCheckSummary(total_findings=1, passed=1, failed=0, errors=0, total_cases=1, approved_cases=1),
            comparisons=[],
            evaluations=[
                ThresholdEvaluationResult(
                    status="PASS",
                    family=MetricFamily.NUMERIC,
                    path="/score",
                    metric_id="m_numeric",
                    key="mean",
                    rule_source="metric-family",
                    rule_form="max_abs_delta",
                    message="ok",
                )
            ],
            current_metrics=[],
        ),
    )
    exit_code = main(
        [
            "drift",
            "check",
            "--suite",
            "suite.yaml",
            "--metrics",
            "metrics.yaml",
            "--baseline",
            "baseline.json",
            "--thresholds",
            "thresholds.yaml",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "DRIFT SUMMARY total_metrics=1 pass=1 fail=0 error=0 cases=1 approved=1\n"


def test_drift_check_fail_exit_1_prints_only_fail_error_lines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_drift_runner(
        monkeypatch,
        lambda **_: None,
        lambda **_: DriftCheckRunResult(
            status="FAIL",
            suite_path="suite.yaml",
            metrics_config_path="metrics.yaml",
            thresholds_config_path="thresholds.yaml",
            baseline_path="baseline.json",
            summary=DriftCheckSummary(total_findings=3, passed=1, failed=1, errors=1, total_cases=3, approved_cases=2),
            comparisons=[],
            evaluations=[
                ThresholdEvaluationResult(
                    status="PASS",
                    family=MetricFamily.NUMERIC,
                    path="/a",
                    metric_id="a",
                    key="mean",
                    rule_source="metric-family",
                    rule_form="max_abs_delta",
                    message="ok",
                ),
                ThresholdEvaluationResult(
                    status="FAIL",
                    family=MetricFamily.PRESENCE,
                    path="/b",
                    metric_id="b",
                    key="presence_rate",
                    rule_source="per-key",
                    rule_form="max_rate_delta",
                    message="Threshold check failed.",
                ),
                ThresholdEvaluationResult(
                    status="ERROR",
                    family=MetricFamily.COVERAGE,
                    path="/c",
                    metric_id="c",
                    key=None,
                    rule_source="none",
                    rule_form=None,
                    message="Comparator produced error result.",
                ),
            ],
            current_metrics=[],
        ),
    )
    exit_code = main(
        [
            "drift",
            "check",
            "--suite",
            "suite.yaml",
            "--metrics",
            "metrics.yaml",
            "--baseline",
            "baseline.json",
            "--thresholds",
            "thresholds.yaml",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == (
        "DRIFT SUMMARY total_metrics=3 pass=1 fail=1 error=1 cases=3 approved=2\n"
        "METRIC FAIL presence /b b.presence_rate baseline=None current=None delta=None threshold=-\n"
        "METRIC ERROR coverage /c c Comparator produced error result.\n"
    )


def test_drift_check_error_exit_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_drift_runner(
        monkeypatch,
        lambda **_: None,
        lambda **_: DriftCheckRunResult(
            status="ERROR",
            suite_path="suite.yaml",
            metrics_config_path="metrics.yaml",
            thresholds_config_path="thresholds.yaml",
            baseline_path="baseline.json",
            summary=DriftCheckSummary(total_findings=1, passed=0, failed=0, errors=1, total_cases=1, approved_cases=0),
            comparisons=[],
            evaluations=[
                ThresholdEvaluationResult(
                    status="ERROR",
                    family=MetricFamily.COVERAGE,
                    path="/c",
                    metric_id="c",
                    key=None,
                    rule_source="none",
                    rule_form=None,
                    message="error",
                )
            ],
            current_metrics=[],
        ),
    )
    exit_code = main(
        [
            "drift",
            "check",
            "--suite",
            "suite.yaml",
            "--metrics",
            "metrics.yaml",
            "--baseline",
            "baseline.json",
            "--thresholds",
            "thresholds.yaml",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == (
        "DRIFT SUMMARY total_metrics=1 pass=0 fail=0 error=1 cases=1 approved=0\n"
        "METRIC ERROR coverage /c c error\n"
    )


def test_drift_check_runner_error_exit_2(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_fake_drift_runner(
        monkeypatch,
        lambda **_: None,
        lambda **_: SentinelError(category="SCHEMA_INVALID", code="SENTINEL_X", message="bad"),
    )
    exit_code = main(
        [
            "drift",
            "check",
            "--suite",
            "suite.yaml",
            "--metrics",
            "metrics.yaml",
            "--baseline",
            "baseline.json",
            "--thresholds",
            "thresholds.yaml",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == "DRIFT CHECK ERROR\nSCHEMA_INVALID SENTINEL_X bad\n"
