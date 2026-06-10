"""Drift deterministic metric comparator."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.drift.types import MetricFamily, MetricResultRecord


@dataclass(frozen=True, slots=True)
class MetricComparisonResult:
    """Machine-readable comparison for one metric record."""

    status: Literal["PASS", "ERROR"]
    family: MetricFamily
    path: str
    metric_id: str
    key: str | None
    baseline_value: float | None
    current_value: float | None
    delta: float | None
    error_code: str | None = None
    message: str | None = None
    is_rate_metric: bool = False


@dataclass(frozen=True, slots=True)
class MetricGroupComparisonResult:
    """Machine-readable key-set comparison for one metric group."""

    family: MetricFamily
    path: str
    metric_id: str
    baseline_keys: tuple[str, ...]
    current_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricComparisonOutput:
    """Comparator output payload for threshold evaluation."""

    metric_results: list[MetricComparisonResult]
    group_results: list[MetricGroupComparisonResult]


def _comparison_error(
    *,
    family: MetricFamily,
    path: str,
    metric_id: str,
    key: str | None,
    error_code: str,
    message: str,
) -> MetricComparisonResult:
    return MetricComparisonResult(
        status="ERROR",
        family=family,
        path=path,
        metric_id=metric_id,
        key=key,
        baseline_value=None,
        current_value=None,
        delta=None,
        error_code=error_code,
        message=message,
        is_rate_metric=(key or "").endswith("_rate"),
    )


def _sort_key(
    family: MetricFamily,
    path: str,
    metric_id: str,
    key: str | None,
) -> tuple[str, str, str, str]:
    return (family.value, path, metric_id, key or "")


def _index_metrics(
    metrics: list[MetricResultRecord],
    dataset_name: str,
) -> tuple[dict[tuple[MetricFamily, str, str, str | None], MetricResultRecord], list[MetricComparisonResult]]:
    index: dict[tuple[MetricFamily, str, str, str | None], MetricResultRecord] = {}
    errors: list[MetricComparisonResult] = []
    for record in metrics:
        if not math.isfinite(record.value):
            errors.append(
                _comparison_error(
                    family=record.family,
                    path=record.path,
                    metric_id=record.metric_id,
                    key=record.key,
                    error_code="SENTINEL_DRIFT_COMPARE_INVALID_METRIC_INPUT",
                    message=f"{dataset_name} metric value must be finite.",
                )
            )
            continue

        identity = (record.family, record.path, record.metric_id, record.key)
        if identity in index:
            errors.append(
                _comparison_error(
                    family=record.family,
                    path=record.path,
                    metric_id=record.metric_id,
                    key=record.key,
                    error_code="SENTINEL_DRIFT_COMPARE_DUPLICATE_METRIC",
                    message=f"{dataset_name} contains duplicate metric record identity.",
                )
            )
            continue
        index[identity] = record
    return index, errors


def compare_metrics(
    baseline_metrics: list[MetricResultRecord],
    current_metrics: list[MetricResultRecord],
) -> MetricComparisonOutput:
    """Compare current metrics against baseline metrics deterministically."""
    baseline_index, baseline_errors = _index_metrics(baseline_metrics, "baseline")
    current_index, current_errors = _index_metrics(current_metrics, "current")

    metric_results: list[MetricComparisonResult] = [*baseline_errors, *current_errors]

    ordered_current_keys = sorted(current_index.keys(), key=lambda item: _sort_key(*item))
    for identity in ordered_current_keys:
        family, path, metric_id, key = identity
        current = current_index[identity]
        baseline = baseline_index.get(identity)
        if baseline is None:
            metric_results.append(
                _comparison_error(
                    family=family,
                    path=path,
                    metric_id=metric_id,
                    key=key,
                    error_code="SENTINEL_DRIFT_COMPARE_MISSING_BASELINE_METRIC",
                    message="Current metric has no matching baseline metric.",
                )
            )
            continue

        delta = current.value - baseline.value
        metric_results.append(
            MetricComparisonResult(
                status="PASS",
                family=family,
                path=path,
                metric_id=metric_id,
                key=key,
                baseline_value=baseline.value,
                current_value=current.value,
                delta=delta,
                is_rate_metric=(key or "").endswith("_rate"),
            )
        )

    for identity in sorted(baseline_index.keys(), key=lambda item: _sort_key(*item)):
        if identity in current_index:
            continue
        family, path, metric_id, key = identity
        metric_results.append(
            _comparison_error(
                family=family,
                path=path,
                metric_id=metric_id,
                key=key,
                error_code="SENTINEL_DRIFT_COMPARE_INVALID_METRIC_INPUT",
                message="Current metrics are missing baseline metric identity.",
            )
        )

    group_keys: set[tuple[MetricFamily, str, str]] = set()
    for family, path, metric_id, _ in baseline_index:
        group_keys.add((family, path, metric_id))
    for family, path, metric_id, _ in current_index:
        group_keys.add((family, path, metric_id))

    group_results: list[MetricGroupComparisonResult] = []
    for family, path, metric_id in sorted(group_keys, key=lambda item: (item[0].value, item[1], item[2])):
        baseline_keys = sorted(
            identity[3] or "" for identity in baseline_index if identity[0:3] == (family, path, metric_id)
        )
        current_keys = sorted(
            identity[3] or "" for identity in current_index if identity[0:3] == (family, path, metric_id)
        )
        group_results.append(
            MetricGroupComparisonResult(
                family=family,
                path=path,
                metric_id=metric_id,
                baseline_keys=tuple(baseline_keys),
                current_keys=tuple(current_keys),
            )
        )

    metric_results = sorted(
        metric_results, key=lambda item: _sort_key(item.family, item.path, item.metric_id, item.key)
    )
    return MetricComparisonOutput(metric_results=metric_results, group_results=group_results)


def validate_comparison_output(output: MetricComparisonOutput) -> SentinelError | None:
    """Validate comparator output payload shape."""
    for index, item in enumerate(output.metric_results):
        if item.status not in {"PASS", "ERROR"}:
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_DRIFT_COMPARE_INVALID_STATUS",
                message="Comparator result has invalid status.",
                details={"index": index, "status": item.status},
            )
    return None
