"""Drift drift config loader and strict validation."""

from __future__ import annotations

import os
from typing import Any

import yaml

from sentinel.core.errors import SCHEMA_INVALID, SentinelError, file_not_found, file_read_error
from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdRuleDefinition
from sentinel.drift.types import MetricDefinition, MetricFamily, MetricsConfig

_FORBIDDEN_STATISTICAL_FIELDS: tuple[str, ...] = (
    "avg",
    "average",
    "bucket",
    "buckets",
    "confidence",
    "distribution",
    "embedding",
    "embeddings",
    "histogram",
    "ks_test",
    "median",
    "p50",
    "p90",
    "p95",
    "p99",
    "percentile",
    "percentiles",
    "probability",
    "quantile",
    "quantiles",
    "semantic",
    "stdev",
    "stddev",
    "t_test",
    "variance",
    "z_score",
)


class _UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"Duplicate key '{key}'")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(  # type: ignore[arg-type]
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _drift_error(code: str, message: str, details: dict[str, object] | None = None) -> SentinelError:
    return SentinelError(
        category=SCHEMA_INVALID,
        code=code,
        message=message,
        details=details,
    )


def _load_yaml(path: str) -> dict[str, Any] | SentinelError:
    if not os.path.exists(path):
        return file_not_found(path)

    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:  # noqa: BLE001
        return file_read_error(path, str(exc))

    try:
        loaded = yaml.load(raw, Loader=_UniqueKeyLoader)  # noqa: S506
    except ValueError as exc:
        return _drift_error(
            code="SENTINEL_DRIFT_DUPLICATE_KEY",
            message="YAML contains duplicate keys.",
            details={"path": path, "error": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001
        return _drift_error(
            code="SENTINEL_DRIFT_INVALID_YAML",
            message="Config file is not valid YAML.",
            details={"path": path, "error": str(exc)},
        )

    if not isinstance(loaded, dict):
        return _drift_error(
            code="SENTINEL_DRIFT_INVALID_TOP_LEVEL",
            message="Config top-level YAML must be a mapping.",
            details={"path": path},
        )
    return loaded


def _reject_unknown_fields(
    *,
    allowed: set[str],
    raw: dict[str, Any],
    code: str,
    message: str,
    details: dict[str, object],
) -> SentinelError | None:
    unknown = sorted(key for key in raw if key not in allowed)
    if unknown:
        payload = dict(details)
        payload["unknown_fields"] = unknown
        return _drift_error(code=code, message=message, details=payload)
    return None


def _reject_forbidden_fields(raw: dict[str, Any], details: dict[str, object]) -> SentinelError | None:
    forbidden = sorted(key for key in raw if key in _FORBIDDEN_STATISTICAL_FIELDS)
    if forbidden:
        payload = dict(details)
        payload["forbidden_fields"] = forbidden
        return _drift_error(
            code="SENTINEL_DRIFT_FORBIDDEN_FIELD",
            message="Probabilistic or statistical fields are not allowed.",
            details=payload,
        )
    return None


def load_metrics_config(metrics_path: str) -> MetricsConfig | SentinelError:
    """Load and validate drift metrics config."""
    loaded = _load_yaml(metrics_path)
    if isinstance(loaded, SentinelError):
        return loaded

    unknown_top = _reject_unknown_fields(
        allowed={"metrics"},
        raw=loaded,
        code="SENTINEL_DRIFT_METRICS_UNKNOWN_TOP_FIELD",
        message="Metrics config contains unknown top-level fields.",
        details={"path": metrics_path},
    )
    if unknown_top is not None:
        return unknown_top

    raw_metrics = loaded.get("metrics")
    if raw_metrics is None:
        return _drift_error(
            code="SENTINEL_DRIFT_METRICS_MISSING_METRICS",
            message="Metrics config must include field 'metrics'.",
            details={"path": metrics_path},
        )
    if not isinstance(raw_metrics, list):
        return _drift_error(
            code="SENTINEL_DRIFT_METRICS_INVALID_METRICS_TYPE",
            message="Metrics config field 'metrics' must be a list.",
            details={"path": metrics_path},
        )
    if len(raw_metrics) == 0:
        return _drift_error(
            code="SENTINEL_DRIFT_METRICS_EMPTY_METRICS",
            message="Metrics config 'metrics' must be a non-empty list.",
            details={"path": metrics_path},
        )

    seen_ids: set[str] = set()
    metrics: list[MetricDefinition] = []
    for idx, raw_metric in enumerate(raw_metrics):
        if not isinstance(raw_metric, dict):
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_INVALID_METRIC_TYPE",
                message="Each metric definition must be a mapping.",
                details={"path": metrics_path, "metric_index": idx},
            )

        forbidden = _reject_forbidden_fields(
            raw_metric,
            {"path": metrics_path, "metric_index": idx},
        )
        if forbidden is not None:
            return forbidden

        unknown_metric = _reject_unknown_fields(
            allowed={"metric_id", "family", "path", "key"},
            raw=raw_metric,
            code="SENTINEL_DRIFT_METRICS_UNKNOWN_FIELD",
            message="Metric definition contains unknown fields.",
            details={"path": metrics_path, "metric_index": idx},
        )
        if unknown_metric is not None:
            return unknown_metric

        metric_id = raw_metric.get("metric_id")
        if metric_id is None or not isinstance(metric_id, str) or metric_id == "":
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_MISSING_ID",
                message="Each metric definition must include non-empty string field 'metric_id'.",
                details={"path": metrics_path, "metric_index": idx},
            )
        if metric_id in seen_ids:
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_DUPLICATE_ID",
                message="Metric definition ids must be unique.",
                details={"path": metrics_path, "metric_id": metric_id},
            )
        seen_ids.add(metric_id)

        family_raw = raw_metric.get("family")
        if family_raw is None or not isinstance(family_raw, str):
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_MISSING_FAMILY",
                message="Each metric definition must include string field 'family'.",
                details={"path": metrics_path, "metric_id": metric_id},
            )
        try:
            family = MetricFamily(family_raw)
        except ValueError:
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_UNSUPPORTED_FAMILY",
                message="Metric definition uses unsupported metric family.",
                details={"path": metrics_path, "metric_id": metric_id, "family": family_raw},
            )

        metric_path = raw_metric.get("path")
        if metric_path is None or not isinstance(metric_path, str) or metric_path == "":
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_MISSING_PATH",
                message="Each metric definition must include non-empty string field 'path'.",
                details={"path": metrics_path, "metric_id": metric_id},
            )

        key = raw_metric.get("key")
        if key is not None and (not isinstance(key, str) or key == ""):
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_INVALID_KEY_TYPE",
                message="Metric definition field 'key' must be a non-empty string when present.",
                details={"path": metrics_path, "metric_id": metric_id},
            )

        requires_key = family is MetricFamily.OBJECT_KEY_PRESENCE
        if requires_key and key is None:
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_MISSING_KEY",
                message="Metric family 'object_key_presence' requires field 'key'.",
                details={"path": metrics_path, "metric_id": metric_id},
            )
        if not requires_key and key is not None:
            return _drift_error(
                code="SENTINEL_DRIFT_METRICS_UNEXPECTED_KEY",
                message="Metric definition field 'key' is only valid for 'object_key_presence'.",
                details={"path": metrics_path, "metric_id": metric_id},
            )

        metrics.append(
            MetricDefinition(
                metric_id=metric_id,
                family=family,
                path=metric_path,
                key=key,
            )
        )

    return MetricsConfig(metrics=metrics)


def _parse_threshold_rule(
    *,
    raw_rule: Any,
    details: dict[str, object],
) -> ThresholdRuleDefinition | SentinelError:
    if not isinstance(raw_rule, dict):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_RULE_TYPE",
            message="Each threshold rule must be a mapping.",
            details=details,
        )

    forbidden = _reject_forbidden_fields(raw_rule, details)
    if forbidden is not None:
        return forbidden

    unknown_rule = _reject_unknown_fields(
        allowed={"max_abs_delta", "max_rate_delta", "require_exact_match", "allowed_values", "strict_key_set"},
        raw=raw_rule,
        code="SENTINEL_DRIFT_THRESHOLDS_UNKNOWN_RULE_FIELD",
        message="Threshold rule contains unknown fields.",
        details=details,
    )
    if unknown_rule is not None:
        return unknown_rule

    max_abs_delta = raw_rule.get("max_abs_delta")
    if max_abs_delta is not None and not isinstance(max_abs_delta, (int, float)):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_MAX_ABS_DELTA_TYPE",
            message="Threshold field 'max_abs_delta' must be numeric.",
            details=details,
        )
    if isinstance(max_abs_delta, (int, float)) and max_abs_delta < 0:
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_NEGATIVE_MAX_ABS_DELTA",
            message="Threshold field 'max_abs_delta' must be non-negative.",
            details=details,
        )

    max_rate_delta = raw_rule.get("max_rate_delta")
    if max_rate_delta is not None and not isinstance(max_rate_delta, (int, float)):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_MAX_RATE_DELTA_TYPE",
            message="Threshold field 'max_rate_delta' must be numeric.",
            details=details,
        )
    if isinstance(max_rate_delta, (int, float)) and max_rate_delta < 0:
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_NEGATIVE_MAX_RATE_DELTA",
            message="Threshold field 'max_rate_delta' must be non-negative.",
            details=details,
        )

    require_exact_match = raw_rule.get("require_exact_match")
    if require_exact_match is not None and not isinstance(require_exact_match, bool):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_REQUIRE_EXACT_MATCH_TYPE",
            message="Threshold field 'require_exact_match' must be boolean.",
            details=details,
        )

    allowed_values_raw = raw_rule.get("allowed_values")
    allowed_values: tuple[float, ...] | None = None
    if allowed_values_raw is not None:
        if not isinstance(allowed_values_raw, list):
            return _drift_error(
                code="SENTINEL_DRIFT_THRESHOLDS_INVALID_ALLOWED_VALUES_TYPE",
                message="Threshold field 'allowed_values' must be a list of numbers.",
                details=details,
            )
        normalized_allowed: list[float] = []
        for item in allowed_values_raw:
            if not isinstance(item, (int, float)) or isinstance(item, bool):
                return _drift_error(
                    code="SENTINEL_DRIFT_THRESHOLDS_INVALID_ALLOWED_VALUES_ITEM_TYPE",
                    message="Threshold field 'allowed_values' must be a list of numbers.",
                    details=details,
                )
            normalized_allowed.append(float(item))
        allowed_values = tuple(normalized_allowed)

    strict_key_set_raw = raw_rule.get("strict_key_set")
    strict_key_set: tuple[str, ...] | None = None
    if strict_key_set_raw is not None:
        if not isinstance(strict_key_set_raw, list):
            return _drift_error(
                code="SENTINEL_DRIFT_THRESHOLDS_INVALID_STRICT_KEY_SET_TYPE",
                message="Threshold field 'strict_key_set' must be a list of non-empty strings.",
                details=details,
            )
        normalized_keys: list[str] = []
        for item in strict_key_set_raw:
            if not isinstance(item, str) or item == "":
                return _drift_error(
                    code="SENTINEL_DRIFT_THRESHOLDS_INVALID_STRICT_KEY_SET_ITEM_TYPE",
                    message="Threshold field 'strict_key_set' must be a list of non-empty strings.",
                    details=details,
                )
            normalized_keys.append(item)
        strict_key_set = tuple(sorted(normalized_keys))

    return ThresholdRuleDefinition(
        max_abs_delta=None if max_abs_delta is None else float(max_abs_delta),
        max_rate_delta=None if max_rate_delta is None else float(max_rate_delta),
        require_exact_match=require_exact_match,
        allowed_values=allowed_values,
        strict_key_set=strict_key_set,
    )


def load_thresholds_config(thresholds_path: str) -> ThresholdConfig | SentinelError:
    """Load and validate drift thresholds config."""
    loaded = _load_yaml(thresholds_path)
    if isinstance(loaded, SentinelError):
        return loaded

    unknown_top = _reject_unknown_fields(
        allowed={"global", "metric_family", "per_key", "per_path"},
        raw=loaded,
        code="SENTINEL_DRIFT_THRESHOLDS_UNKNOWN_TOP_FIELD",
        message="Thresholds config contains unknown top-level fields.",
        details={"path": thresholds_path},
    )
    if unknown_top is not None:
        return unknown_top

    global_rule: ThresholdRuleDefinition | None = None
    if "global" in loaded:
        global_rule_result = _parse_threshold_rule(
            raw_rule=loaded["global"],
            details={"path": thresholds_path, "scope": "global"},
        )
        if isinstance(global_rule_result, SentinelError):
            return global_rule_result
        global_rule = global_rule_result

    family_rules: dict[MetricFamily, ThresholdRuleDefinition] = {}
    raw_family = loaded.get("metric_family", {})
    if not isinstance(raw_family, dict):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_METRIC_FAMILY_TYPE",
            message="Thresholds field 'metric_family' must be a mapping.",
            details={"path": thresholds_path},
        )
    for family_name in sorted(raw_family):
        try:
            family = MetricFamily(family_name)
        except ValueError:
            return _drift_error(
                code="SENTINEL_DRIFT_THRESHOLDS_UNSUPPORTED_FAMILY",
                message="Thresholds field 'metric_family' includes unsupported metric family.",
                details={"path": thresholds_path, "family": family_name},
            )
        rule_result = _parse_threshold_rule(
            raw_rule=raw_family[family_name],
            details={"path": thresholds_path, "scope": "metric_family", "family": family_name},
        )
        if isinstance(rule_result, SentinelError):
            return rule_result
        family_rules[family] = rule_result

    path_rules: dict[str, ThresholdRuleDefinition] = {}
    raw_paths = loaded.get("per_path", {})
    if not isinstance(raw_paths, dict):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_PER_PATH_TYPE",
            message="Thresholds field 'per_path' must be a mapping.",
            details={"path": thresholds_path},
        )
    for metric_path in sorted(raw_paths):
        if not isinstance(metric_path, str) or metric_path == "":
            return _drift_error(
                code="SENTINEL_DRIFT_THRESHOLDS_INVALID_PER_PATH_KEY",
                message="Thresholds field 'per_path' keys must be non-empty strings.",
                details={"path": thresholds_path},
            )
        rule_result = _parse_threshold_rule(
            raw_rule=raw_paths[metric_path],
            details={"path": thresholds_path, "scope": "per_path", "metric_path": metric_path},
        )
        if isinstance(rule_result, SentinelError):
            return rule_result
        path_rules[metric_path] = rule_result

    key_rules: dict[str, ThresholdRuleDefinition] = {}
    raw_keys = loaded.get("per_key", {})
    if not isinstance(raw_keys, dict):
        return _drift_error(
            code="SENTINEL_DRIFT_THRESHOLDS_INVALID_PER_KEY_TYPE",
            message="Thresholds field 'per_key' must be a mapping.",
            details={"path": thresholds_path},
        )
    for key_name in sorted(raw_keys):
        if not isinstance(key_name, str) or key_name == "":
            return _drift_error(
                code="SENTINEL_DRIFT_THRESHOLDS_INVALID_PER_KEY_KEY",
                message="Thresholds field 'per_key' keys must be non-empty strings.",
                details={"path": thresholds_path},
            )
        rule_result = _parse_threshold_rule(
            raw_rule=raw_keys[key_name],
            details={"path": thresholds_path, "scope": "per_key", "key": key_name},
        )
        if isinstance(rule_result, SentinelError):
            return rule_result
        key_rules[key_name] = rule_result

    return ThresholdConfig(
        per_key=key_rules,
        per_path=path_rules,
        metric_family=family_rules,
        global_rule=global_rule,
    )
