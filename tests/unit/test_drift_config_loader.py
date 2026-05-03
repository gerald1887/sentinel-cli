"""Unit tests for Drift drift config loader."""

from __future__ import annotations

from pathlib import Path

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.drift.config_loader import load_metrics_config, load_thresholds_config
from sentinel.drift.threshold_engine import ThresholdConfig
from sentinel.drift.types import MetricFamily, MetricsConfig


def _write_yaml(tmp_path: Path, content: str, name: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_load_metrics_config_valid_success(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: m_coverage
    family: coverage
    path: /answer
  - metric_id: m_object_key
    family: object_key_presence
    path: /payload
    key: status
""",
        "metrics.yaml",
    )
    result = load_metrics_config(metrics_path)
    assert isinstance(result, MetricsConfig)
    assert [metric.metric_id for metric in result.metrics] == ["m_coverage", "m_object_key"]
    assert result.metrics[0].family is MetricFamily.COVERAGE
    assert result.metrics[1].family is MetricFamily.OBJECT_KEY_PRESENCE
    assert result.metrics[1].key == "status"


def test_load_thresholds_config_valid_success(tmp_path: Path) -> None:
    thresholds_path = _write_yaml(
        tmp_path,
        """
global:
  max_abs_delta: 0.2
metric_family:
  numeric:
    max_abs_delta: 1
per_path:
  /answer/score:
    max_abs_delta: 0.5
per_key:
  m_numeric:
    max_abs_delta: 0.1
""",
        "thresholds.yaml",
    )
    result = load_thresholds_config(thresholds_path)
    assert isinstance(result, ThresholdConfig)
    assert result.global_rule is not None
    assert result.global_rule.max_abs_delta == 0.2
    assert result.metric_family[MetricFamily.NUMERIC].max_abs_delta == 1.0
    assert result.per_path["/answer/score"].max_abs_delta == 0.5
    assert result.per_key["m_numeric"].max_abs_delta == 0.1


def test_load_metrics_config_missing_required_field_fails(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: missing_family
    path: /x
""",
        "metrics_missing.yaml",
    )
    result = load_metrics_config(metrics_path)
    assert isinstance(result, SentinelError)
    assert result.category == SCHEMA_INVALID
    assert result.code == "SENTINEL_DRIFT_METRICS_MISSING_FAMILY"


def test_load_thresholds_config_missing_required_field_fails(tmp_path: Path) -> None:
    thresholds_path = _write_yaml(
        tmp_path,
        """
global:
  unexpected: 1
""",
        "thresholds_missing.yaml",
    )
    result = load_thresholds_config(thresholds_path)
    assert isinstance(result, SentinelError)
    assert result.category == SCHEMA_INVALID
    assert result.code == "SENTINEL_DRIFT_THRESHOLDS_UNKNOWN_RULE_FIELD"


def test_load_metrics_config_unknown_field_fails(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: m1
    family: coverage
    path: /x
    random_field: true
""",
        "metrics_unknown.yaml",
    )
    result = load_metrics_config(metrics_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_METRICS_UNKNOWN_FIELD"
    assert result.details == {
        "metric_index": 0,
        "path": metrics_path,
        "unknown_fields": ["random_field"],
    }


def test_load_thresholds_config_unknown_field_fails(tmp_path: Path) -> None:
    thresholds_path = _write_yaml(
        tmp_path,
        """
global:
  max_abs_delta: 0.2
extra_top: true
""",
        "thresholds_unknown.yaml",
    )
    result = load_thresholds_config(thresholds_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_THRESHOLDS_UNKNOWN_TOP_FIELD"
    assert result.details == {"path": thresholds_path, "unknown_fields": ["extra_top"]}


def test_load_metrics_config_duplicate_metric_ids_fail(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: dup
    family: coverage
    path: /x
  - metric_id: dup
    family: presence
    path: /x
""",
        "metrics_duplicate_id.yaml",
    )
    result = load_metrics_config(metrics_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_METRICS_DUPLICATE_ID"


def test_load_thresholds_config_duplicate_definition_fail(tmp_path: Path) -> None:
    thresholds_path = _write_yaml(
        tmp_path,
        """
per_key:
  id1:
    max_abs_delta: 0.1
  id1:
    max_abs_delta: 0.2
""",
        "thresholds_duplicate_key.yaml",
    )
    result = load_thresholds_config(thresholds_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_DUPLICATE_KEY"


def test_load_metrics_config_unsupported_family_fails(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: m1
    family: semantic_similarity
    path: /x
""",
        "metrics_unsupported_family.yaml",
    )
    result = load_metrics_config(metrics_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_METRICS_UNSUPPORTED_FAMILY"


def test_load_thresholds_config_unsupported_family_fails(tmp_path: Path) -> None:
    thresholds_path = _write_yaml(
        tmp_path,
        """
metric_family:
  semantic_similarity:
    max_abs_delta: 0.1
""",
        "thresholds_unsupported_family.yaml",
    )
    result = load_thresholds_config(thresholds_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_THRESHOLDS_UNSUPPORTED_FAMILY"


def test_load_metrics_config_forbidden_statistical_fields_fails(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: m1
    family: numeric
    path: /x
    p95: 0.9
""",
        "metrics_forbidden.yaml",
    )
    result = load_metrics_config(metrics_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_FORBIDDEN_FIELD"
    assert result.details == {
        "metric_index": 0,
        "path": metrics_path,
        "forbidden_fields": ["p95"],
    }


def test_load_thresholds_config_forbidden_statistical_fields_fails(tmp_path: Path) -> None:
    thresholds_path = _write_yaml(
        tmp_path,
        """
global:
  max_abs_delta: 0.1
  p99: 0.9
""",
        "thresholds_forbidden.yaml",
    )
    result = load_thresholds_config(thresholds_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_DRIFT_FORBIDDEN_FIELD"
    assert result.details == {
        "path": thresholds_path,
        "scope": "global",
        "forbidden_fields": ["p99"],
    }


def test_validation_unknown_field_order_is_deterministic(tmp_path: Path) -> None:
    metrics_path = _write_yaml(
        tmp_path,
        """
metrics:
  - metric_id: m1
    family: coverage
    path: /x
    zzz: true
    aaa: true
""",
        "metrics_unknown_order.yaml",
    )
    first = load_metrics_config(metrics_path)
    second = load_metrics_config(metrics_path)
    assert isinstance(first, SentinelError)
    assert isinstance(second, SentinelError)
    assert first.code == second.code == "SENTINEL_DRIFT_METRICS_UNKNOWN_FIELD"
    assert first.details == second.details == {
        "metric_index": 0,
        "path": metrics_path,
        "unknown_fields": ["aaa", "zzz"],
    }
