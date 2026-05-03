"""Unit tests for Drift deterministic metric engine."""

from __future__ import annotations

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.drift.metric_engine import SuiteCoverageSummary, compute_metrics
from sentinel.drift.types import MetricDefinition, MetricFamily, MetricsConfig


def _config(metrics: list[MetricDefinition]) -> MetricsConfig:
    return MetricsConfig(metrics=metrics)


def test_compute_coverage_metric() -> None:
    outputs = []
    cfg = _config(
        [
            MetricDefinition(metric_id="m_coverage", family=MetricFamily.COVERAGE, path="/coverage"),
        ]
    )
    result = compute_metrics(
        cfg,
        outputs,
        suite_coverage_summary=SuiteCoverageSummary(
            total_cases=10,
            executed_cases=8,
            approved_cases=6,
            error_cases=2,
        ),
    )
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("approval_rate", 0.75),
        ("approved_cases", 6.0),
        ("error_cases", 2.0),
        ("executed_cases", 8.0),
        ("total_cases", 10.0),
    ]


def test_compute_presence_metric() -> None:
    outputs = [{"a": 1}, {"a": 2}, {"b": 3}]
    cfg = _config(
        [
            MetricDefinition(metric_id="m_presence", family=MetricFamily.PRESENCE, path="/a"),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("absence_count", 1.0),
        ("presence_count", 2.0),
        ("presence_rate", (2.0 / 3.0)),
    ]


def test_compute_presence_metric_empty_outputs_is_deterministic() -> None:
    cfg = _config(
        [
            MetricDefinition(metric_id="m_presence", family=MetricFamily.PRESENCE, path="/a"),
        ]
    )
    result = compute_metrics(cfg, [])
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("absence_count", 0.0),
        ("presence_count", 0.0),
        ("presence_rate", 0.0),
    ]


def test_compute_scalar_distributions_metric() -> None:
    outputs = [{"state": "ok"}, {"state": "warn"}, {"state": "ok"}]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_scalar_dist",
                family=MetricFamily.SCALAR_DISTRIBUTIONS,
                path="/state",
            ),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("str:ok", 2.0),
        ("str:warn", 1.0),
    ]


def test_compute_numeric_metric() -> None:
    outputs = [{"score": 1}, {"score": 2}, {"score": 4}]
    cfg = _config(
        [
            MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/score"),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("max", 4.0),
        ("mean", (7.0 / 3.0)),
        ("min", 1.0),
    ]


def test_compute_string_length_metric() -> None:
    outputs = [{"name": "a"}, {"name": "abcd"}]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_string_len",
                family=MetricFamily.STRING_LENGTH,
                path="/name",
            ),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("max", 4.0),
        ("mean", 2.5),
        ("min", 1.0),
    ]


def test_compute_array_length_metric() -> None:
    outputs = [{"items": [1, 2]}, {"items": [7]}, {"items": [4, 5, 6]}]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_array_len",
                family=MetricFamily.ARRAY_LENGTH,
                path="/items",
            ),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("max", 3.0),
        ("mean", 2.0),
        ("min", 1.0),
    ]


def test_compute_object_key_presence_metric() -> None:
    outputs = [
        {"obj": {"status": "ok", "id": "1"}},
        {"obj": {"id": "2"}},
        {"obj": {"status": "warn", "id": "3"}},
    ]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_key_presence",
                family=MetricFamily.OBJECT_KEY_PRESENCE,
                path="/obj",
                key="status",
            ),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert len(result) == 1
    assert result[0].key == "status"
    assert result[0].value == (2.0 / 3.0)


def test_compute_assertion_outcomes_metric() -> None:
    outputs = [{"x": 1}]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_assertions",
                family=MetricFamily.ASSERTION_OUTCOMES,
                path="/",
            ),
        ]
    )
    result = compute_metrics(
        cfg,
        outputs,
        assertion_outcomes=["PASS", "FAIL", "PASS", "ERROR"],
    )
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("ERROR", 0.25),
        ("FAIL", 0.25),
        ("PASS", 0.5),
    ]


def test_metric_ordering_is_deterministic() -> None:
    outputs = [
        {"n": 3, "state": "b"},
        {"n": 1, "state": "a"},
        {"n": 2, "state": "b"},
    ]
    cfg = _config(
        [
            MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/n"),
            MetricDefinition(
                metric_id="m_scalar_dist",
                family=MetricFamily.SCALAR_DISTRIBUTIONS,
                path="/state",
            ),
        ]
    )
    first = compute_metrics(cfg, outputs)
    second = compute_metrics(cfg, outputs)
    assert not isinstance(first, SentinelError)
    assert not isinstance(second, SentinelError)
    assert [(item.metric_id, item.key, item.value) for item in first] == [
        ("m_numeric", "max", 3.0),
        ("m_numeric", "mean", 2.0),
        ("m_numeric", "min", 1.0),
        ("m_scalar_dist", "str:a", 1.0),
        ("m_scalar_dist", "str:b", 2.0),
    ]
    assert [(item.metric_id, item.key, item.value) for item in first] == [
        (item.metric_id, item.key, item.value) for item in second
    ]


def test_missing_path_fails_deterministically() -> None:
    outputs = [{"x": 1}, {"x": 2}]
    cfg = _config(
        [
            MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/missing"),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert isinstance(result, SentinelError)
    assert result.category == SCHEMA_INVALID
    assert result.code == "SENTINEL_DRIFT_METRIC_PATH_NOT_FOUND"
    assert result.details == {
        "metric_id": "m_numeric",
        "path": "/missing",
        "output_index": 0,
    }


def test_type_mismatch_fails_deterministically() -> None:
    outputs = [{"name": "abc"}, {"name": 123}]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_string_len",
                family=MetricFamily.STRING_LENGTH,
                path="/name",
            ),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_METRIC_TYPE_MISMATCH"
    assert result.details == {
        "metric_id": "m_string_len",
        "path": "/name",
        "output_index": 1,
        "expected": "string",
    }


def test_invalid_json_pointer_fails_deterministically() -> None:
    outputs = [{"x": 1}]
    cfg = _config(
        [
            MetricDefinition(metric_id="m_presence", family=MetricFamily.PRESENCE, path="not_pointer"),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_METRIC_INVALID_PATH"
    assert result.details == {"metric_id": "m_presence", "path": "not_pointer"}


def test_presence_missing_path_does_not_fail() -> None:
    outputs = [{"x": 1}, {"x": 2}]
    cfg = _config(
        [
            MetricDefinition(metric_id="m_presence", family=MetricFamily.PRESENCE, path="/missing"),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert not isinstance(result, SentinelError)
    assert [(item.key, item.value) for item in result] == [
        ("absence_count", 2.0),
        ("presence_count", 0.0),
        ("presence_rate", 0.0),
    ]


def test_coverage_requires_summary_input() -> None:
    cfg = _config(
        [
            MetricDefinition(metric_id="m_coverage", family=MetricFamily.COVERAGE, path="/coverage"),
        ]
    )
    result = compute_metrics(cfg, [])
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_COVERAGE_MISSING_SUMMARY"


def test_non_coverage_family_with_empty_outputs_fails() -> None:
    cfg = _config(
        [
            MetricDefinition(metric_id="m_numeric", family=MetricFamily.NUMERIC, path="/n"),
        ]
    )
    result = compute_metrics(cfg, [])
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_METRICS_EMPTY_APPROVED_OUTPUTS"


def test_assertion_outcomes_missing_input_fails() -> None:
    outputs = [{"x": 1}]
    cfg = _config(
        [
            MetricDefinition(
                metric_id="m_assertions",
                family=MetricFamily.ASSERTION_OUTCOMES,
                path="/",
            ),
        ]
    )
    result = compute_metrics(cfg, outputs)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_ASSERTIONS_MISSING_INPUT"
