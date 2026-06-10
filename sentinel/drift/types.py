"""Drift drift detection data types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal


class MetricFamily(StrEnum):
    """Supported deterministic metric families."""

    COVERAGE = "coverage"
    PRESENCE = "presence"
    SCALAR_DISTRIBUTIONS = "scalar_distributions"
    NUMERIC = "numeric"
    STRING_LENGTH = "string_length"
    ARRAY_LENGTH = "array_length"
    OBJECT_KEY_PRESENCE = "object_key_presence"
    ASSERTION_OUTCOMES = "assertion_outcomes"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Single explicit metric definition from config."""

    metric_id: str
    family: MetricFamily
    path: str
    key: str | None = None


@dataclass(frozen=True, slots=True)
class MetricsConfig:
    """Validated metrics configuration."""

    metrics: list[MetricDefinition]


@dataclass(frozen=True, slots=True)
class ThresholdRule:
    """Deterministic threshold rule payload."""

    max_delta: float


THRESHOLD_PRECEDENCE: tuple[str, ...] = (
    "per-key",
    "per-path",
    "metric-family",
    "global",
)


@dataclass(frozen=True, slots=True)
class ThresholdsConfig:
    """Validated thresholds configuration."""

    per_key: dict[str, ThresholdRule]
    per_path: dict[str, ThresholdRule]
    metric_family: dict[MetricFamily, ThresholdRule]
    global_rule: ThresholdRule | None = None


BASELINE_VERSION: str = "1.0"


@dataclass(frozen=True, slots=True)
class BaselineEnvelope:
    """Baseline payload envelope for Drift artifacts."""

    version: Literal["1.0"]
    suite: str
    metrics: list[MetricResultRecord]


@dataclass(frozen=True, slots=True)
class MetricResultRecord:
    """Normalized metric output record."""

    metric_id: str
    family: MetricFamily
    path: str
    key: str | None
    value: float


@dataclass(frozen=True, slots=True)
class DriftResultRecord:
    """Deterministic drift comparison record."""

    metric_id: str
    family: MetricFamily
    path: str
    key: str | None
    baseline_value: float
    current_value: float
    delta: float
    status: Literal["PASS", "FAIL"]
