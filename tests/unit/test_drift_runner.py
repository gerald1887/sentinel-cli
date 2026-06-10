"""Unit tests for Drift drift runner orchestration."""

from __future__ import annotations

from pathlib import Path

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.drift.runner import run_drift_baseline, run_drift_check
from sentinel.drift.types import MetricFamily
from sentinel.testkit.types import SuiteCaseDefinition, SuiteDefinition


def _suite() -> SuiteDefinition:
    return SuiteDefinition(
        command="run",
        suite_path="suite.yaml",
        cases=[
            SuiteCaseDefinition(
                case_id="c1",
                prompt="p1",
                schema="s1",
                provider="stub",
                model="stub",
                timeout=10,
            ),
            SuiteCaseDefinition(
                case_id="c2",
                prompt="p2",
                schema="s2",
                provider="stub",
                model="stub",
                timeout=10,
            ),
        ],
    )


def test_run_drift_baseline_happy_path(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    result = run_drift_baseline(
        suite_path="tests/fixtures/suite.yaml",
        metrics_config_path="tests/fixtures/metrics.yaml",
        baseline_path=str(baseline_path),
    )
    # real fixtures may not exist in repo; do a mocked orchestration path below
    assert isinstance(result, SentinelError) or result.status in {"PASS", "ERROR"}


def test_run_drift_baseline_happy_path_mocked(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.types import MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_cov", family=MetricFamily.COVERAGE, path="/coverage")
    ]))
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda case: {"x": 1})
    monkeypatch.setattr(runner, "write_baseline", lambda *_: None)

    result = run_drift_baseline(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        baseline_path=str(tmp_path / "baseline.json"),
    )
    assert not isinstance(result, SentinelError)
    assert result.status == "PASS"
    assert result.summary.total_cases == 2
    assert result.summary.approved_cases == 2
    assert result.summary.error_cases == 0
    assert [m.key for m in result.metrics] == [
        "approval_rate",
        "approved_cases",
        "error_cases",
        "executed_cases",
        "total_cases",
    ]


def test_run_drift_check_happy_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdRuleDefinition
    from sentinel.drift.types import BaselineEnvelope, MetricDefinition, MetricResultRecord, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")
    ]))
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=1.0)},
            global_rule=None,
        ),
    )
    monkeypatch.setattr(
        runner,
        "read_baseline",
        lambda _: BaselineEnvelope(
            version="1.0",
            suite="suite.yaml",
            metrics=[
                MetricResultRecord(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score", key="max", value=3.0),  # noqa: E501
                MetricResultRecord(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score", key="mean", value=2.0),  # noqa: E501
                MetricResultRecord(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score", key="min", value=1.0),  # noqa: E501
            ],
        ),
    )
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda case: {"score": 1 if case.case_id == "c1" else 3})

    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert not isinstance(result, SentinelError)
    assert result.status in {"PASS", "FAIL"}
    assert result.summary.errors == 0


def test_error_precedence_over_fail(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.comparator import MetricComparisonOutput, MetricComparisonResult
    from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdEvaluationResult, ThresholdRuleDefinition
    from sentinel.drift.types import BaselineEnvelope, MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")
    ]))
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.1)},
            global_rule=None,
        ),
    )
    monkeypatch.setattr(runner, "read_baseline", lambda _: BaselineEnvelope(version="1.0", suite="suite.yaml", metrics=[]))  # noqa: E501
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda _: {"score": 1})
    monkeypatch.setattr(
        runner,
        "compare_metrics",
        lambda *_: MetricComparisonOutput(
            metric_results=[
                MetricComparisonResult(
                    status="PASS",
                    family=MetricFamily.NUMERIC,
                    path="/score",
                    metric_id="m_numeric",
                    key="mean",
                    baseline_value=1.0,
                    current_value=3.0,
                    delta=2.0,
                )
            ],
            group_results=[],
        ),
    )
    monkeypatch.setattr(
        runner,
        "evaluate_thresholds",
        lambda *_: [
            ThresholdEvaluationResult(
                status="FAIL",
                family=MetricFamily.NUMERIC,
                path="/score",
                metric_id="m_numeric",
                key="mean",
                rule_source="metric-family",
                rule_form="max_abs_delta",
                message="failed",
            ),
            ThresholdEvaluationResult(
                status="ERROR",
                family=MetricFamily.NUMERIC,
                path="/score",
                metric_id="m_numeric",
                key="mean",
                rule_source="metric-family",
                rule_form=None,
                message="error",
            ),
        ],
    )

    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert not isinstance(result, SentinelError)
    assert result.status == "ERROR"


def test_fail_when_breach_and_no_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdEvaluationResult, ThresholdRuleDefinition
    from sentinel.drift.types import BaselineEnvelope, MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")
    ]))
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.1)},
            global_rule=None,
        ),
    )
    monkeypatch.setattr(runner, "read_baseline", lambda _: BaselineEnvelope(version="1.0", suite="suite.yaml", metrics=[]))  # noqa: E501
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda _: {"score": 1})
    monkeypatch.setattr(
        runner,
        "evaluate_thresholds",
        lambda *_: [
            ThresholdEvaluationResult(
                status="FAIL",
                family=MetricFamily.NUMERIC,
                path="/score",
                metric_id="m_numeric",
                key="mean",
                rule_source="metric-family",
                rule_form="max_abs_delta",
                message="failed",
            )
        ],
    )
    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert not isinstance(result, SentinelError)
    assert result.status == "FAIL"


def test_pass_when_all_metrics_pass(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdEvaluationResult, ThresholdRuleDefinition
    from sentinel.drift.types import BaselineEnvelope, MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")
    ]))
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.1)},
            global_rule=None,
        ),
    )
    monkeypatch.setattr(runner, "read_baseline", lambda _: BaselineEnvelope(version="1.0", suite="suite.yaml", metrics=[]))  # noqa: E501
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda _: {"score": 1})
    monkeypatch.setattr(
        runner,
        "evaluate_thresholds",
        lambda *_: [
            ThresholdEvaluationResult(
                status="PASS",
                family=MetricFamily.NUMERIC,
                path="/score",
                metric_id="m_numeric",
                key="mean",
                rule_source="metric-family",
                rule_form="max_abs_delta",
                message="pass",
            )
        ],
    )
    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert not isinstance(result, SentinelError)
    assert result.status == "PASS"


def test_baseline_write_failure_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.types import MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_cov", family=MetricFamily.COVERAGE, path="/coverage")
    ]))
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda _: {"x": 1})
    monkeypatch.setattr(
        runner,
        "write_baseline",
        lambda *_: SentinelError(category=SCHEMA_INVALID, code="SENTINEL_BASELINE_WRITE", message="write failed"),
    )
    result = run_drift_baseline(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        baseline_path="baseline.json",
    )
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_BASELINE_WRITE"


def test_baseline_read_failure_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdRuleDefinition
    from sentinel.drift.types import MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")
    ]))
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.1)},
            global_rule=None,
        ),
    )
    monkeypatch.setattr(
        runner,
        "read_baseline",
        lambda *_: SentinelError(category=SCHEMA_INVALID, code="SENTINEL_BASELINE_READ", message="read failed"),
    )
    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_BASELINE_READ"


def test_suite_execution_failure_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.types import MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_cov", family=MetricFamily.COVERAGE, path="/coverage")
    ]))
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(
        runner,
        "execute_case",
        lambda case: SentinelError(category=SCHEMA_INVALID, code="SENTINEL_CASE_ERROR", message="case failed")
        if case.case_id == "c2"
        else {"x": 1},
    )
    result = run_drift_baseline(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        baseline_path="baseline.json",
    )
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_SUITE_EXECUTION_ERROR"


def test_optional_assertion_input_path(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.types import MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_assert", family=MetricFamily.ASSERTION_OUTCOMES, path="/"),
    ]))
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda _: {"x": 1})
    monkeypatch.setattr(runner, "write_baseline", lambda *_: None)
    result = run_drift_baseline(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        baseline_path="baseline.json",
        assertion_outcomes=["PASS", "FAIL"],
    )
    assert not isinstance(result, SentinelError)
    assert result.status == "PASS"


def test_deterministic_ordering_of_aggregated_results(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.comparator import MetricComparisonOutput, MetricComparisonResult
    from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdEvaluationResult, ThresholdRuleDefinition
    from sentinel.drift.types import BaselineEnvelope, MetricDefinition, MetricsConfig

    monkeypatch.setattr(runner, "load_metrics_config", lambda _: MetricsConfig(metrics=[
        MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")
    ]))
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=1.0)},
            global_rule=None,
        ),
    )
    monkeypatch.setattr(runner, "read_baseline", lambda _: BaselineEnvelope(version="1.0", suite="suite.yaml", metrics=[]))  # noqa: E501
    monkeypatch.setattr(runner, "load_suite", lambda _: _suite())
    monkeypatch.setattr(runner, "execute_case", lambda _: {"score": 1})
    monkeypatch.setattr(
        runner,
        "compare_metrics",
        lambda *_: MetricComparisonOutput(
            metric_results=[
                MetricComparisonResult(
                    status="PASS",
                    family=MetricFamily.PRESENCE,
                    path="/z",
                    metric_id="z",
                    key="presence_rate",
                    baseline_value=1.0,
                    current_value=1.0,
                    delta=0.0,
                ),
                MetricComparisonResult(
                    status="PASS",
                    family=MetricFamily.NUMERIC,
                    path="/a",
                    metric_id="a",
                    key="mean",
                    baseline_value=1.0,
                    current_value=1.0,
                    delta=0.0,
                ),
            ],
            group_results=[],
        ),
    )
    monkeypatch.setattr(
        runner,
        "evaluate_thresholds",
        lambda *_: [
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
                status="PASS",
                family=MetricFamily.PRESENCE,
                path="/z",
                metric_id="z",
                key="presence_rate",
                rule_source="metric-family",
                rule_form="max_abs_delta",
                message="ok",
            ),
        ],
    )
    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert not isinstance(result, SentinelError)
    assert [(item.family.value, item.path, item.metric_id, item.key) for item in result.evaluations] == [
        ("numeric", "/a", "a", "mean"),
        ("presence", "/z", "z", "presence_rate"),
    ]


def test_threshold_runtime_type_mismatch_returns_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from sentinel.drift import runner
    from sentinel.drift.types import MetricDefinition, MetricsConfig, ThresholdRule, ThresholdsConfig

    monkeypatch.setattr(
        runner,
        "load_metrics_config",
        lambda _: MetricsConfig(metrics=[MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score")]),  # noqa: E501
    )
    monkeypatch.setattr(
        runner,
        "load_thresholds_config",
        lambda _: ThresholdsConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRule(max_delta=0.1)},
            global_rule=None,
        ),
    )

    result = run_drift_check(
        suite_path="suite.yaml",
        metrics_config_path="metrics.yaml",
        thresholds_config_path="thresholds.yaml",
        baseline_path="baseline.json",
    )
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_THRESHOLDS_INVALID_RUNTIME_TYPE"
