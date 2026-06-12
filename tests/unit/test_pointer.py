"""Unit tests for the shared JSON Pointer resolver (sentinel.core.pointer).

Covers root-document shorthands and verifies the resolver is
correctly threaded through the guardrail and drift evaluation layers.
"""

from __future__ import annotations

import pytest

from sentinel.core.pointer import resolve_json_pointer

# ---------------------------------------------------------------------------
# Direct resolver — root shorthands
# ---------------------------------------------------------------------------

class TestRootShorthands:
    """Empty string and '/' both refer to the whole document (RFC 6901)."""

    def test_empty_string_returns_full_document(self) -> None:
        doc = {"a": 1, "b": [2, 3]}
        found, value = resolve_json_pointer(doc, "")
        assert found is True
        assert value is doc

    def test_slash_returns_full_document(self) -> None:
        doc = {"a": 1, "b": [2, 3]}
        found, value = resolve_json_pointer(doc, "/")
        assert found is True
        assert value is doc

    def test_empty_string_on_scalar_document(self) -> None:
        found, value = resolve_json_pointer(42, "")
        assert found is True
        assert value == 42

    def test_slash_on_scalar_document(self) -> None:
        found, value = resolve_json_pointer(42, "/")
        assert found is True
        assert value == 42

    def test_empty_string_on_list_document(self) -> None:
        doc = [1, 2, 3]
        found, value = resolve_json_pointer(doc, "")
        assert found is True
        assert value is doc

    def test_slash_on_list_document(self) -> None:
        doc = [1, 2, 3]
        found, value = resolve_json_pointer(doc, "/")
        assert found is True
        assert value is doc


# ---------------------------------------------------------------------------
# Direct resolver — non-root paths
# ---------------------------------------------------------------------------

class TestNonRootPaths:
    """Standard pointer paths and missing-path cases."""

    def test_nested_path_resolves_to_value(self) -> None:
        doc = {"outer": {"inner": "found"}}
        found, value = resolve_json_pointer(doc, "/outer/inner")
        assert found is True
        assert value == "found"

    def test_missing_path_returns_false_and_none(self) -> None:
        doc = {"a": 1}
        found, value = resolve_json_pointer(doc, "/missing")
        assert found is False
        assert value is None

    def test_deep_missing_path_returns_false_and_none(self) -> None:
        doc = {"a": {"b": 1}}
        found, value = resolve_json_pointer(doc, "/a/c")
        assert found is False
        assert value is None

    def test_malformed_pointer_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            resolve_json_pointer({"a": 1}, "a")  # no leading slash


# ---------------------------------------------------------------------------
# Guard resolution path — shorthands via evaluate_assertions
# ---------------------------------------------------------------------------

class TestRootShorthandsViaGuard:
    """Root shorthands reach the resolver through the guardrail evaluator."""

    def test_empty_string_exists_assertion_passes(self) -> None:
        from sentinel.guardrail.evaluator import evaluate_assertions

        result = evaluate_assertions(
            input_json={"key": "value"},
            assertions=[{"id": "root_check", "type": "exists", "path": ""}],
        )
        assert result.assertions[0].status == "PASS"

    def test_slash_exists_assertion_passes(self) -> None:
        from sentinel.guardrail.evaluator import evaluate_assertions

        result = evaluate_assertions(
            input_json={"key": "value"},
            assertions=[{"id": "root_check", "type": "exists", "path": "/"}],
        )
        assert result.assertions[0].status == "PASS"


# ---------------------------------------------------------------------------
# Drift metric resolution path — shorthands via compute_metrics
# ---------------------------------------------------------------------------

class TestRootShorthandsViaDrift:
    """Root shorthands reach the resolver through the drift metric engine."""

    def test_empty_string_presence_metric_counts_root_as_present(self) -> None:
        from sentinel.core.errors import SentinelError
        from sentinel.drift.metric_engine import compute_metrics
        from sentinel.drift.types import MetricDefinition, MetricFamily, MetricsConfig

        cfg = MetricsConfig(metrics=[
            MetricDefinition(metric_id="m", family=MetricFamily.PRESENCE, path=""),
        ])
        result = compute_metrics(cfg, [{"a": 1}, {"b": 2}])
        assert not isinstance(result, SentinelError)
        presence = {r.key: r.value for r in result}
        assert presence["presence_count"] == 2.0
        assert presence["absence_count"] == 0.0

    def test_slash_presence_metric_counts_root_as_present(self) -> None:
        from sentinel.core.errors import SentinelError
        from sentinel.drift.metric_engine import compute_metrics
        from sentinel.drift.types import MetricDefinition, MetricFamily, MetricsConfig

        cfg = MetricsConfig(metrics=[
            MetricDefinition(metric_id="m", family=MetricFamily.PRESENCE, path="/"),
        ])
        result = compute_metrics(cfg, [{"a": 1}, {"b": 2}])
        assert not isinstance(result, SentinelError)
        presence = {r.key: r.value for r in result}
        assert presence["presence_count"] == 2.0
        assert presence["absence_count"] == 0.0

    def test_empty_string_numeric_metric_resolves_scalar_root(self) -> None:
        from sentinel.core.errors import SentinelError
        from sentinel.drift.metric_engine import compute_metrics
        from sentinel.drift.types import MetricDefinition, MetricFamily, MetricsConfig

        cfg = MetricsConfig(metrics=[
            MetricDefinition(metric_id="m_num", family=MetricFamily.NUMERIC, path=""),
        ])
        result = compute_metrics(cfg, [1.0, 2.0, 3.0])
        assert not isinstance(result, SentinelError)
        metrics = {r.key: r.value for r in result}
        assert metrics["min"] == 1.0
        assert metrics["max"] == 3.0

    def test_slash_numeric_metric_resolves_scalar_root(self) -> None:
        from sentinel.core.errors import SentinelError
        from sentinel.drift.metric_engine import compute_metrics
        from sentinel.drift.types import MetricDefinition, MetricFamily, MetricsConfig

        cfg = MetricsConfig(metrics=[
            MetricDefinition(metric_id="m_num", family=MetricFamily.NUMERIC, path="/"),
        ])
        result = compute_metrics(cfg, [1.0, 2.0, 3.0])
        assert not isinstance(result, SentinelError)
        metrics = {r.key: r.value for r in result}
        assert metrics["min"] == 1.0
        assert metrics["max"] == 3.0
