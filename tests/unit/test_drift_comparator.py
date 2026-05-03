"""Unit tests for Drift metric comparator."""

from __future__ import annotations

from sentinel.drift.comparator import compare_metrics
from sentinel.drift.types import MetricFamily, MetricResultRecord


def _metric(
    metric_id: str,
    family: MetricFamily,
    path: str,
    key: str | None,
    value: float,
) -> MetricResultRecord:
    return MetricResultRecord(metric_id=metric_id, family=family, path=path, key=key, value=value)


def test_compare_metrics_computes_delta() -> None:
    baseline = [_metric("m_numeric", MetricFamily.NUMERIC, "/score", "mean", 2.0)]
    current = [_metric("m_numeric", MetricFamily.NUMERIC, "/score", "mean", 2.5)]
    result = compare_metrics(baseline, current)

    assert len(result.metric_results) == 1
    item = result.metric_results[0]
    assert item.status == "PASS"
    assert item.delta == 0.5
    assert item.baseline_value == 2.0
    assert item.current_value == 2.5


def test_missing_baseline_metric_is_error() -> None:
    result = compare_metrics([], [_metric("m_numeric", MetricFamily.NUMERIC, "/score", "mean", 2.5)])
    assert len(result.metric_results) == 1
    item = result.metric_results[0]
    assert item.status == "ERROR"
    assert item.error_code == "SENTINEL_DRIFT_COMPARE_MISSING_BASELINE_METRIC"


def test_missing_current_metric_is_invalid_input_error() -> None:
    result = compare_metrics([_metric("m_numeric", MetricFamily.NUMERIC, "/score", "mean", 2.0)], [])
    assert len(result.metric_results) == 1
    item = result.metric_results[0]
    assert item.status == "ERROR"
    assert item.error_code == "SENTINEL_DRIFT_COMPARE_INVALID_METRIC_INPUT"


def test_invalid_metric_input_nan_is_error() -> None:
    baseline = [_metric("m_numeric", MetricFamily.NUMERIC, "/score", "mean", float("nan"))]
    current = [_metric("m_numeric", MetricFamily.NUMERIC, "/score", "mean", 2.0)]
    result = compare_metrics(baseline, current)
    assert any(item.error_code == "SENTINEL_DRIFT_COMPARE_INVALID_METRIC_INPUT" for item in result.metric_results)


def test_deterministic_ordering_of_findings() -> None:
    baseline = [
        _metric("z_metric", MetricFamily.PRESENCE, "/z", "presence_rate", 1.0),
        _metric("a_metric", MetricFamily.NUMERIC, "/a", "mean", 1.0),
    ]
    current = [
        _metric("a_metric", MetricFamily.NUMERIC, "/a", "mean", 2.0),
        _metric("z_metric", MetricFamily.PRESENCE, "/z", "presence_rate", 1.0),
    ]
    result = compare_metrics(baseline, current)
    assert [(item.family.value, item.path, item.metric_id, item.key) for item in result.metric_results] == [
        ("numeric", "/a", "a_metric", "mean"),
        ("presence", "/z", "z_metric", "presence_rate"),
    ]


def test_group_key_results_are_deterministic() -> None:
    baseline = [
        _metric("m_presence", MetricFamily.PRESENCE, "/user", "absence_count", 0.0),
        _metric("m_presence", MetricFamily.PRESENCE, "/user", "presence_count", 2.0),
    ]
    current = [
        _metric("m_presence", MetricFamily.PRESENCE, "/user", "presence_count", 1.0),
        _metric("m_presence", MetricFamily.PRESENCE, "/user", "presence_rate", 0.5),
    ]
    result = compare_metrics(baseline, current)
    assert len(result.group_results) == 1
    group = result.group_results[0]
    assert group.baseline_keys == ("absence_count", "presence_count")
    assert group.current_keys == ("presence_count", "presence_rate")
