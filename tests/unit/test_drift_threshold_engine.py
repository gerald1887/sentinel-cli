"""Unit tests for Drift threshold evaluation."""

from __future__ import annotations

from sentinel.drift.comparator import MetricComparisonOutput, MetricComparisonResult, MetricGroupComparisonResult
from sentinel.drift.threshold_engine import (
    ThresholdConfig,
    ThresholdRuleDefinition,
    evaluate_thresholds,
)
from sentinel.drift.types import MetricFamily


def _comparison(
    *,
    family: MetricFamily = MetricFamily.NUMERIC,
    path: str = "/score",
    metric_id: str = "m_numeric",
    key: str | None = "mean",
    baseline_value: float = 2.0,
    current_value: float = 2.1,
    delta: float = 0.1,
    status: str = "PASS",
    is_rate_metric: bool = False,
) -> MetricComparisonResult:
    return MetricComparisonResult(
        status=status,  # type: ignore[arg-type]
        family=family,
        path=path,
        metric_id=metric_id,
        key=key,
        baseline_value=baseline_value,
        current_value=current_value,
        delta=delta,
        is_rate_metric=is_rate_metric,
    )


def _output(results: list[MetricComparisonResult], groups: list[MetricGroupComparisonResult] | None = None) -> MetricComparisonOutput:
    return MetricComparisonOutput(metric_results=results, group_results=[] if groups is None else groups)


def test_threshold_max_abs_delta_boundary_pass_and_fail() -> None:
    config = ThresholdConfig(
        per_key={},
        per_path={},
        metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.1)},
        global_rule=None,
    )
    passing = evaluate_thresholds(_output([_comparison(delta=0.1)]), config)[0]
    failing = evaluate_thresholds(_output([_comparison(delta=0.11)]), config)[0]
    assert passing.status == "PASS"
    assert failing.status == "FAIL"
    assert failing.rule_form == "max_abs_delta"


def test_threshold_precedence_per_key_overrides_others() -> None:
    config = ThresholdConfig(
        per_key={"mean": ThresholdRuleDefinition(max_abs_delta=0.2)},
        per_path={"/score": ThresholdRuleDefinition(max_abs_delta=0.01)},
        metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.01)},
        global_rule=ThresholdRuleDefinition(max_abs_delta=0.01),
    )
    result = evaluate_thresholds(_output([_comparison(delta=0.15)]), config)[0]
    assert result.status == "PASS"
    assert result.rule_source == "per-key"


def test_threshold_precedence_per_path_when_no_per_key() -> None:
    config = ThresholdConfig(
        per_key={},
        per_path={"/score": ThresholdRuleDefinition(max_abs_delta=0.2)},
        metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.01)},
        global_rule=ThresholdRuleDefinition(max_abs_delta=0.01),
    )
    result = evaluate_thresholds(_output([_comparison(delta=0.15)]), config)[0]
    assert result.status == "PASS"
    assert result.rule_source == "per-path"


def test_threshold_precedence_metric_family_when_no_higher_rule() -> None:
    config = ThresholdConfig(
        per_key={},
        per_path={},
        metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.2)},
        global_rule=ThresholdRuleDefinition(max_abs_delta=0.01),
    )
    result = evaluate_thresholds(_output([_comparison(delta=0.15)]), config)[0]
    assert result.status == "PASS"
    assert result.rule_source == "metric-family"


def test_threshold_precedence_global_when_no_other_rule() -> None:
    config = ThresholdConfig(
        per_key={},
        per_path={},
        metric_family={},
        global_rule=ThresholdRuleDefinition(max_abs_delta=0.2),
    )
    result = evaluate_thresholds(_output([_comparison(delta=0.15)]), config)[0]
    assert result.status == "PASS"
    assert result.rule_source == "global"


def test_require_exact_match() -> None:
    config = ThresholdConfig(
        per_key={"mean": ThresholdRuleDefinition(require_exact_match=True)},
        per_path={},
        metric_family={},
        global_rule=None,
    )
    pass_result = evaluate_thresholds(_output([_comparison(delta=0.0, current_value=2.0)]), config)[0]
    fail_result = evaluate_thresholds(_output([_comparison(delta=0.1, current_value=2.1)]), config)[0]
    assert pass_result.status == "PASS"
    assert fail_result.status == "FAIL"
    assert fail_result.rule_form == "require_exact_match"


def test_allowed_values() -> None:
    config = ThresholdConfig(
        per_key={"mean": ThresholdRuleDefinition(allowed_values=(1.0, 2.1))},
        per_path={},
        metric_family={},
        global_rule=None,
    )
    pass_result = evaluate_thresholds(_output([_comparison(current_value=2.1)]), config)[0]
    fail_result = evaluate_thresholds(_output([_comparison(current_value=3.5)]), config)[0]
    assert pass_result.status == "PASS"
    assert fail_result.status == "FAIL"
    assert fail_result.rule_form == "allowed_values"


def test_max_rate_delta_only_for_rate_metrics() -> None:
    config = ThresholdConfig(
        per_key={"presence_rate": ThresholdRuleDefinition(max_rate_delta=0.1)},
        per_path={},
        metric_family={},
        global_rule=ThresholdRuleDefinition(max_rate_delta=0.1),
    )
    pass_result = evaluate_thresholds(
        _output([_comparison(key="presence_rate", delta=0.05, is_rate_metric=True)]),
        config,
    )[0]
    error_result = evaluate_thresholds(
        _output([_comparison(key="mean", delta=0.05, is_rate_metric=False)]),
        config,
    )[0]
    assert pass_result.status == "PASS"
    assert error_result.status == "ERROR"


def test_missing_baseline_metric_error_propagates() -> None:
    result = _comparison(status="ERROR")  # type: ignore[arg-type]
    config = ThresholdConfig(per_key={}, per_path={}, metric_family={}, global_rule=None)
    evaluated = evaluate_thresholds(_output([result]), config)[0]
    assert evaluated.status == "ERROR"


def test_strict_key_set_supported() -> None:
    config = ThresholdConfig(
        per_key={},
        per_path={"/user": ThresholdRuleDefinition(strict_key_set=("absence_count", "presence_count", "presence_rate"))},
        metric_family={},
        global_rule=None,
    )
    group = MetricGroupComparisonResult(
        family=MetricFamily.PRESENCE,
        path="/user",
        metric_id="m_presence",
        baseline_keys=("absence_count", "presence_count", "presence_rate"),
        current_keys=("absence_count", "presence_count"),
    )
    evaluated = evaluate_thresholds(_output([], [group]), config)[0]
    assert evaluated.status == "FAIL"
    assert evaluated.rule_form == "strict_key_set"


