"""Unit tests for Drift drift types."""

from __future__ import annotations

from sentinel.drift.types import (
    BASELINE_VERSION,
    THRESHOLD_PRECEDENCE,
    BaselineEnvelope,
    DriftResultRecord,
    MetricDefinition,
    MetricFamily,
    MetricResultRecord,
    ThresholdRule,
    ThresholdsConfig,
)


def test_metric_family_values_are_locked() -> None:
    assert [family.value for family in MetricFamily] == [
        "coverage",
        "presence",
        "scalar_distributions",
        "numeric",
        "string_length",
        "array_length",
        "object_key_presence",
        "assertion_outcomes",
    ]


def test_threshold_precedence_constant_is_locked() -> None:
    assert THRESHOLD_PRECEDENCE == ("per-key", "per-path", "metric-family", "global")


def test_baseline_version_is_static_literal() -> None:
    assert BASELINE_VERSION == "1.0"
    envelope = BaselineEnvelope(
        version="1.0",
        suite="suite.yaml",
        metrics=[],
    )
    assert envelope.version == "1.0"


def test_metric_result_and_drift_result_records_construct() -> None:
    metric = MetricResultRecord(
        metric_id="m1",
        family=MetricFamily.NUMERIC,
        path="/price",
        key=None,
        value=10.0,
    )
    drift = DriftResultRecord(
        metric_id="m1",
        family=MetricFamily.NUMERIC,
        path="/price",
        key=None,
        baseline_value=10.0,
        current_value=10.5,
        delta=0.5,
        status="FAIL",
    )
    assert metric.metric_id == "m1"
    assert drift.status == "FAIL"


def test_thresholds_config_uses_explicit_scopes() -> None:
    config = ThresholdsConfig(
        per_key={"m1": ThresholdRule(max_delta=0.1)},
        per_path={"/price": ThresholdRule(max_delta=0.2)},
        metric_family={MetricFamily.NUMERIC: ThresholdRule(max_delta=0.3)},
        global_rule=ThresholdRule(max_delta=0.4),
    )
    assert config.per_key["m1"].max_delta == 0.1
    assert config.per_path["/price"].max_delta == 0.2
    assert config.metric_family[MetricFamily.NUMERIC].max_delta == 0.3
    assert config.global_rule is not None
