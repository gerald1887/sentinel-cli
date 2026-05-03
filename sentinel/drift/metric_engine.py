"""Drift deterministic metric computation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.drift.types import MetricDefinition, MetricFamily, MetricResultRecord, MetricsConfig


@dataclass(frozen=True, slots=True)
class SuiteCoverageSummary:
    """Suite-level deterministic counts required for coverage metrics."""

    total_cases: int
    executed_cases: int
    approved_cases: int
    error_cases: int


def _metric_error(
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


def _decode_pointer_token(token: str) -> str:
    decoded: list[str] = []
    idx = 0
    while idx < len(token):
        char = token[idx]
        if char != "~":
            decoded.append(char)
            idx += 1
            continue
        if idx + 1 >= len(token):
            raise ValueError("malformed pointer escape")
        next_char = token[idx + 1]
        if next_char == "0":
            decoded.append("~")
        elif next_char == "1":
            decoded.append("/")
        else:
            raise ValueError("malformed pointer escape")
        idx += 2
    return "".join(decoded)


def _resolve_pointer(input_json: object, path: str) -> tuple[bool, object | None]:
    if path == "":
        return True, input_json
    if not path.startswith("/"):
        raise ValueError("malformed pointer path")

    tokens = path[1:].split("/")
    current: object = input_json

    for raw_token in tokens:
        token = _decode_pointer_token(raw_token)
        if isinstance(current, dict):
            if token not in current:
                return False, None
            current = current[token]
            continue
        if isinstance(current, list):
            if token == "-":
                raise ValueError("malformed array index token")
            try:
                index = int(token)
            except ValueError as exc:
                raise ValueError("malformed array index token") from exc
            if str(index) != token:
                raise ValueError("malformed array index token")
            if index < 0 or index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None

    return True, current


def _mean(values: list[float]) -> float:
    return sum(values) / float(len(values))


def _value_token(value: object) -> str:
    if isinstance(value, str):
        return f"str:{value}"
    if isinstance(value, bool):
        return "bool:true" if value else "bool:false"
    if value is None:
        return "null"
    if isinstance(value, int):
        return f"int:{value}"
    return f"float:{value}"


def _resolve_required_values(
    metric: MetricDefinition,
    approved_outputs: list[object],
) -> list[object] | SentinelError:
    if len(approved_outputs) == 0:
        return _metric_error(
            code="SENTINEL_DRIFT_METRICS_EMPTY_APPROVED_OUTPUTS",
            message="This metric family requires non-empty approved outputs input.",
            details={"metric_id": metric.metric_id, "family": metric.family.value},
        )

    values: list[object] = []
    for output_index, output in enumerate(approved_outputs):
        try:
            found, value = _resolve_pointer(output, metric.path)
        except ValueError:
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_INVALID_PATH",
                message="Metric path is not a valid JSON pointer.",
                details={"metric_id": metric.metric_id, "path": metric.path},
            )
        if not found:
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_PATH_NOT_FOUND",
                message="Metric path was not found in approved output.",
                details={
                    "metric_id": metric.metric_id,
                    "path": metric.path,
                    "output_index": output_index,
                },
            )
        values.append(value)
    return values


def _compute_presence(metric: MetricDefinition, approved_outputs: list[object]) -> list[MetricResultRecord] | SentinelError:
    if len(approved_outputs) == 0:
        return [
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key="absence_count",
                value=0.0,
            ),
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key="presence_count",
                value=0.0,
            ),
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key="presence_rate",
                value=0.0,
            ),
        ]

    found_count = 0
    for output in approved_outputs:
        try:
            found, _ = _resolve_pointer(output, metric.path)
        except ValueError:
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_INVALID_PATH",
                message="Metric path is not a valid JSON pointer.",
                details={"metric_id": metric.metric_id, "path": metric.path},
            )
        if found:
            found_count += 1
    absence_count = len(approved_outputs) - found_count
    presence_rate = float(found_count) / float(len(approved_outputs))
    return [
        MetricResultRecord(
            metric_id=metric.metric_id,
            family=metric.family,
            path=metric.path,
            key="absence_count",
            value=float(absence_count),
        ),
        MetricResultRecord(
            metric_id=metric.metric_id,
            family=metric.family,
            path=metric.path,
            key="presence_count",
            value=float(found_count),
        ),
        MetricResultRecord(
            metric_id=metric.metric_id,
            family=metric.family,
            path=metric.path,
            key="presence_rate",
            value=presence_rate,
        ),
    ]


def _compute_coverage_from_summary(
    metric: MetricDefinition,
    suite_summary: SuiteCoverageSummary | None,
) -> list[MetricResultRecord] | SentinelError:
    if suite_summary is None:
        return _metric_error(
            code="SENTINEL_DRIFT_COVERAGE_MISSING_SUMMARY",
            message="Coverage metric requires suite coverage summary input.",
            details={"metric_id": metric.metric_id},
        )

    for field_name, field_value in (
        ("total_cases", suite_summary.total_cases),
        ("executed_cases", suite_summary.executed_cases),
        ("approved_cases", suite_summary.approved_cases),
        ("error_cases", suite_summary.error_cases),
    ):
        if field_value < 0:
            return _metric_error(
                code="SENTINEL_DRIFT_COVERAGE_INVALID_SUMMARY",
                message="Coverage summary fields must be non-negative integers.",
                details={"metric_id": metric.metric_id, "field": field_name},
            )

    approval_rate = 0.0
    if suite_summary.executed_cases > 0:
        approval_rate = float(suite_summary.approved_cases) / float(suite_summary.executed_cases)

    computed = {
        "approval_rate": approval_rate,
        "approved_cases": float(suite_summary.approved_cases),
        "error_cases": float(suite_summary.error_cases),
        "executed_cases": float(suite_summary.executed_cases),
        "total_cases": float(suite_summary.total_cases),
    }
    records: list[MetricResultRecord] = []
    for key in sorted(computed):
        records.append(
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key=key,
                value=computed[key],
            )
        )
    return records


def _compute_scalar_distributions(
    metric: MetricDefinition,
    approved_outputs: list[object],
) -> list[MetricResultRecord] | SentinelError:
    values = _resolve_required_values(metric, approved_outputs)
    if isinstance(values, SentinelError):
        return values

    distribution: dict[str, int] = {}
    for output_index, value in enumerate(values):
        if isinstance(value, (dict, list)):
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_TYPE_MISMATCH",
                message="Metric expects scalar value at path.",
                details={
                    "metric_id": metric.metric_id,
                    "path": metric.path,
                    "output_index": output_index,
                    "expected": "scalar",
                },
            )
        token = _value_token(value)
        distribution[token] = distribution.get(token, 0) + 1

    records: list[MetricResultRecord] = []
    for token in sorted(distribution):
        records.append(
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key=token,
                value=float(distribution[token]),
            )
        )
    return records


def _compute_numeric(metric: MetricDefinition, approved_outputs: list[object]) -> list[MetricResultRecord] | SentinelError:
    values = _resolve_required_values(metric, approved_outputs)
    if isinstance(values, SentinelError):
        return values

    numeric_values: list[float] = []
    for output_index, value in enumerate(values):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_TYPE_MISMATCH",
                message="Metric expects numeric value at path.",
                details={
                    "metric_id": metric.metric_id,
                    "path": metric.path,
                    "output_index": output_index,
                    "expected": "number",
                },
            )
        numeric_values.append(float(value))

    computed = {
        "max": max(numeric_values),
        "mean": _mean(numeric_values),
        "min": min(numeric_values),
    }
    records: list[MetricResultRecord] = []
    for key in sorted(computed):
        records.append(
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key=key,
                value=computed[key],
            )
        )
    return records


def _compute_string_length(
    metric: MetricDefinition,
    approved_outputs: list[object],
) -> list[MetricResultRecord] | SentinelError:
    values = _resolve_required_values(metric, approved_outputs)
    if isinstance(values, SentinelError):
        return values

    lengths: list[float] = []
    for output_index, value in enumerate(values):
        if not isinstance(value, str):
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_TYPE_MISMATCH",
                message="Metric expects string value at path.",
                details={
                    "metric_id": metric.metric_id,
                    "path": metric.path,
                    "output_index": output_index,
                    "expected": "string",
                },
            )
        lengths.append(float(len(value)))

    computed = {
        "max": max(lengths),
        "mean": _mean(lengths),
        "min": min(lengths),
    }
    records: list[MetricResultRecord] = []
    for key in sorted(computed):
        records.append(
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key=key,
                value=computed[key],
            )
        )
    return records


def _compute_array_length(
    metric: MetricDefinition,
    approved_outputs: list[object],
) -> list[MetricResultRecord] | SentinelError:
    values = _resolve_required_values(metric, approved_outputs)
    if isinstance(values, SentinelError):
        return values

    lengths: list[float] = []
    for output_index, value in enumerate(values):
        if not isinstance(value, list):
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_TYPE_MISMATCH",
                message="Metric expects array value at path.",
                details={
                    "metric_id": metric.metric_id,
                    "path": metric.path,
                    "output_index": output_index,
                    "expected": "array",
                },
            )
        lengths.append(float(len(value)))

    computed = {
        "max": max(lengths),
        "mean": _mean(lengths),
        "min": min(lengths),
    }
    records: list[MetricResultRecord] = []
    for key in sorted(computed):
        records.append(
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key=key,
                value=computed[key],
            )
        )
    return records


def _compute_object_key_presence(
    metric: MetricDefinition,
    approved_outputs: list[object],
) -> list[MetricResultRecord] | SentinelError:
    values = _resolve_required_values(metric, approved_outputs)
    if isinstance(values, SentinelError):
        return values

    if metric.key is None:
        return _metric_error(
            code="SENTINEL_DRIFT_METRIC_INVALID_DEFINITION",
            message="Metric definition requires key for object key presence.",
            details={"metric_id": metric.metric_id},
        )

    found_count = 0
    for output_index, value in enumerate(values):
        if not isinstance(value, dict):
            return _metric_error(
                code="SENTINEL_DRIFT_METRIC_TYPE_MISMATCH",
                message="Metric expects object value at path.",
                details={
                    "metric_id": metric.metric_id,
                    "path": metric.path,
                    "output_index": output_index,
                    "expected": "object",
                },
            )
        if metric.key in value:
            found_count += 1

    return [
        MetricResultRecord(
            metric_id=metric.metric_id,
            family=metric.family,
            path=metric.path,
            key=metric.key,
            value=(float(found_count) / float(len(approved_outputs))),
        )
    ]


def _compute_assertion_outcomes(
    metric: MetricDefinition,
    assertion_outcomes: list[str] | None,
) -> list[MetricResultRecord] | SentinelError:
    if assertion_outcomes is None:
        return _metric_error(
            code="SENTINEL_DRIFT_ASSERTIONS_MISSING_INPUT",
            message="Assertion outcomes metric requires assertion outcomes input.",
            details={"metric_id": metric.metric_id},
        )

    if len(assertion_outcomes) == 0:
        return _metric_error(
            code="SENTINEL_DRIFT_ASSERTIONS_EMPTY_INPUT",
            message="Assertion outcomes input must be non-empty.",
            details={"metric_id": metric.metric_id},
        )

    counts: dict[str, int] = {"ERROR": 0, "FAIL": 0, "PASS": 0}
    for status in assertion_outcomes:
        if status not in counts:
            return _metric_error(
                code="SENTINEL_DRIFT_ASSERTIONS_INVALID_STATUS",
                message="Assertion outcomes input contains unsupported status.",
                details={"metric_id": metric.metric_id, "status": status},
            )
        counts[status] += 1

    total = float(len(assertion_outcomes))
    records: list[MetricResultRecord] = []
    for status in sorted(counts):
        records.append(
            MetricResultRecord(
                metric_id=metric.metric_id,
                family=metric.family,
                path=metric.path,
                key=status,
                value=(float(counts[status]) / total),
            )
        )
    return records


def compute_metrics(
    metrics_config: MetricsConfig,
    approved_outputs: list[object],
    assertion_outcomes: list[str] | None = None,
    suite_coverage_summary: SuiteCoverageSummary | None = None,
) -> list[MetricResultRecord] | SentinelError:
    """Compute deterministic configured metrics over approved outputs only."""
    records: list[MetricResultRecord] = []
    for metric in metrics_config.metrics:
        computed: list[MetricResultRecord] | SentinelError
        if metric.family is MetricFamily.COVERAGE:
            computed = _compute_coverage_from_summary(metric, suite_coverage_summary)
        elif metric.family is MetricFamily.PRESENCE:
            computed = _compute_presence(metric, approved_outputs)
        elif metric.family is MetricFamily.SCALAR_DISTRIBUTIONS:
            computed = _compute_scalar_distributions(metric, approved_outputs)
        elif metric.family is MetricFamily.NUMERIC:
            computed = _compute_numeric(metric, approved_outputs)
        elif metric.family is MetricFamily.STRING_LENGTH:
            computed = _compute_string_length(metric, approved_outputs)
        elif metric.family is MetricFamily.ARRAY_LENGTH:
            computed = _compute_array_length(metric, approved_outputs)
        elif metric.family is MetricFamily.OBJECT_KEY_PRESENCE:
            computed = _compute_object_key_presence(metric, approved_outputs)
        elif metric.family is MetricFamily.ASSERTION_OUTCOMES:
            computed = _compute_assertion_outcomes(metric, assertion_outcomes)
        else:
            computed = _metric_error(
                code="SENTINEL_DRIFT_METRICS_UNSUPPORTED_FAMILY",
                message="Metric definition uses unsupported metric family.",
                details={"metric_id": metric.metric_id, "family": metric.family.value},
            )

        if isinstance(computed, SentinelError):
            return computed
        records.extend(computed)

    return records
