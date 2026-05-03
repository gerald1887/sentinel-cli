"""Drift deterministic baseline JSON store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sentinel.core.errors import SCHEMA_INVALID, SentinelError, file_not_found, file_read_error
from sentinel.drift.types import BASELINE_VERSION, BaselineEnvelope, MetricFamily, MetricResultRecord


def _baseline_error(
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> SentinelError:
    return SentinelError(
        category=SCHEMA_INVALID,
        code=code,
        message=message,
        details=details,
    )


def _reject_unknown_fields(
    *,
    raw: dict[str, Any],
    allowed: set[str],
    code: str,
    message: str,
    details: dict[str, object],
) -> SentinelError | None:
    unknown = sorted(key for key in raw if key not in allowed)
    if unknown:
        payload = dict(details)
        payload["unknown_fields"] = unknown
        return _baseline_error(code=code, message=message, details=payload)
    return None


def _parse_metric_payload(raw_metric: Any, index: int, baseline_path: str) -> MetricResultRecord | SentinelError:
    if not isinstance(raw_metric, dict):
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRIC_TYPE",
            message="Each baseline metric entry must be a mapping.",
            details={"path": baseline_path, "metric_index": index},
        )

    unknown = _reject_unknown_fields(
        raw=raw_metric,
        allowed={"family", "key", "metric_id", "path", "value"},
        code="SENTINEL_BASELINE_UNKNOWN_METRIC_FIELD",
        message="Baseline metric entry contains unknown fields.",
        details={"path": baseline_path, "metric_index": index},
    )
    if unknown is not None:
        return unknown

    metric_id = raw_metric.get("metric_id")
    if metric_id is None or not isinstance(metric_id, str) or metric_id == "":
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRIC_ID",
            message="Baseline metric entry requires non-empty string field 'metric_id'.",
            details={"path": baseline_path, "metric_index": index},
        )

    family_raw = raw_metric.get("family")
    if family_raw is None or not isinstance(family_raw, str):
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRIC_FAMILY",
            message="Baseline metric entry requires string field 'family'.",
            details={"path": baseline_path, "metric_index": index, "metric_id": metric_id},
        )
    try:
        family = MetricFamily(family_raw)
    except ValueError:
        return _baseline_error(
            code="SENTINEL_BASELINE_UNSUPPORTED_METRIC_FAMILY",
            message="Baseline metric entry contains unsupported family.",
            details={
                "path": baseline_path,
                "metric_index": index,
                "metric_id": metric_id,
                "family": family_raw,
            },
        )

    metric_path = raw_metric.get("path")
    if metric_path is None or not isinstance(metric_path, str) or metric_path == "":
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRIC_PATH",
            message="Baseline metric entry requires non-empty string field 'path'.",
            details={"path": baseline_path, "metric_index": index, "metric_id": metric_id},
        )

    key = raw_metric.get("key")
    if key is not None and (not isinstance(key, str) or key == ""):
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRIC_KEY",
            message="Baseline metric entry field 'key' must be a non-empty string when present.",
            details={"path": baseline_path, "metric_index": index, "metric_id": metric_id},
        )

    value = raw_metric.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRIC_VALUE",
            message="Baseline metric entry field 'value' must be numeric.",
            details={"path": baseline_path, "metric_index": index, "metric_id": metric_id},
        )

    return MetricResultRecord(
        metric_id=metric_id,
        family=family,
        path=metric_path,
        key=key,
        value=float(value),
    )


def read_baseline(baseline_path: str) -> BaselineEnvelope | SentinelError:
    """Read and validate baseline JSON artifact."""
    if not os.path.exists(baseline_path):
        return file_not_found(baseline_path)

    try:
        with open(baseline_path, encoding="utf-8") as fh:
            raw_text = fh.read()
    except Exception as exc:  # noqa: BLE001
        return file_read_error(baseline_path, str(exc))

    try:
        loaded = json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_JSON",
            message="Baseline file is not valid JSON.",
            details={"path": baseline_path, "error": str(exc)},
        )

    if not isinstance(loaded, dict):
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_TOP_LEVEL",
            message="Baseline top-level JSON must be an object.",
            details={"path": baseline_path},
        )

    unknown_top = _reject_unknown_fields(
        raw=loaded,
        allowed={"metrics", "suite", "version"},
        code="SENTINEL_BASELINE_UNKNOWN_TOP_FIELD",
        message="Baseline contains unknown top-level fields.",
        details={"path": baseline_path},
    )
    if unknown_top is not None:
        return unknown_top

    version = loaded.get("version")
    if version is None or not isinstance(version, str):
        return _baseline_error(
            code="SENTINEL_BASELINE_MISSING_VERSION",
            message="Baseline requires string field 'version'.",
            details={"path": baseline_path},
        )
    if version != BASELINE_VERSION:
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_VERSION",
            message="Baseline version is not supported.",
            details={"path": baseline_path, "version": version, "expected_version": BASELINE_VERSION},
        )

    suite = loaded.get("suite")
    if suite is None or not isinstance(suite, str) or suite == "":
        return _baseline_error(
            code="SENTINEL_BASELINE_MISSING_SUITE",
            message="Baseline requires non-empty string field 'suite'.",
            details={"path": baseline_path},
        )

    raw_metrics = loaded.get("metrics")
    if raw_metrics is None:
        return _baseline_error(
            code="SENTINEL_BASELINE_MISSING_METRICS",
            message="Baseline requires field 'metrics'.",
            details={"path": baseline_path},
        )
    if not isinstance(raw_metrics, list):
        return _baseline_error(
            code="SENTINEL_BASELINE_INVALID_METRICS_TYPE",
            message="Baseline field 'metrics' must be a list.",
            details={"path": baseline_path},
        )

    metrics: list[MetricResultRecord] = []
    for index, raw_metric in enumerate(raw_metrics):
        parsed = _parse_metric_payload(raw_metric, index, baseline_path)
        if isinstance(parsed, SentinelError):
            return parsed
        metrics.append(parsed)

    return BaselineEnvelope(version=BASELINE_VERSION, suite=suite, metrics=metrics)


def write_baseline(baseline_path: str, baseline: BaselineEnvelope) -> SentinelError | None:
    """Write baseline JSON artifact with deterministic formatting."""
    payload = {
        "version": baseline.version,
        "suite": baseline.suite,
        "metrics": [
            {
                "metric_id": item.metric_id,
                "family": item.family.value,
                "path": item.path,
                "key": item.key,
                "value": item.value,
            }
            for item in baseline.metrics
        ],
    }
    try:
        target = Path(baseline_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        target.write_text(encoded, encoding="utf-8")
        return None
    except Exception as exc:  # noqa: BLE001
        return file_read_error(baseline_path, str(exc))
