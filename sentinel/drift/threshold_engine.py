"""Drift deterministic threshold evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sentinel.drift.comparator import (
    MetricComparisonOutput,
    MetricComparisonResult,
    MetricGroupComparisonResult,
)
from sentinel.drift.types import MetricFamily


@dataclass(frozen=True, slots=True)
class ThresholdRuleDefinition:
    """Allowed threshold rule forms only."""

    max_abs_delta: float | None = None
    max_rate_delta: float | None = None
    require_exact_match: bool | None = None
    allowed_values: tuple[float, ...] | None = None
    strict_key_set: tuple[str, ...] | None = None


@dataclass(frozen=True, slots=True)
class ThresholdConfig:
    """Threshold rules grouped by locked precedence scopes."""

    per_key: dict[str, ThresholdRuleDefinition]
    per_path: dict[str, ThresholdRuleDefinition]
    metric_family: dict[MetricFamily, ThresholdRuleDefinition]
    global_rule: ThresholdRuleDefinition | None = None


@dataclass(frozen=True, slots=True)
class ThresholdEvaluationResult:
    """Machine-readable threshold evaluation result."""

    status: Literal["PASS", "FAIL", "ERROR"]
    family: MetricFamily
    path: str
    metric_id: str
    key: str | None
    rule_source: Literal["per-key", "per-path", "metric-family", "global", "none"]
    rule_form: str | None
    message: str
    details: dict[str, object] | None = None


def _error_result(
    *,
    family: MetricFamily,
    path: str,
    metric_id: str,
    key: str | None,
    rule_source: Literal["per-key", "per-path", "metric-family", "global", "none"],
    message: str,
    details: dict[str, object] | None = None,
) -> ThresholdEvaluationResult:
    return ThresholdEvaluationResult(
        status="ERROR",
        family=family,
        path=path,
        metric_id=metric_id,
        key=key,
        rule_source=rule_source,
        rule_form=None,
        message=message,
        details=details,
    )


def _select_rule(
    comparison: MetricComparisonResult,
    config: ThresholdConfig,
) -> tuple[ThresholdRuleDefinition | None, Literal["per-key", "per-path", "metric-family", "global", "none"]]:
    if comparison.key is not None and comparison.key in config.per_key:
        return config.per_key[comparison.key], "per-key"
    if comparison.path in config.per_path:
        return config.per_path[comparison.path], "per-path"
    if comparison.family in config.metric_family:
        return config.metric_family[comparison.family], "metric-family"
    if config.global_rule is not None:
        return config.global_rule, "global"
    return None, "none"


def _evaluate_rule(
    comparison: MetricComparisonResult,
    rule: ThresholdRuleDefinition,
    rule_source: Literal["per-key", "per-path", "metric-family", "global", "none"],
) -> ThresholdEvaluationResult:
    if comparison.status == "ERROR":
        return _error_result(
            family=comparison.family,
            path=comparison.path,
            metric_id=comparison.metric_id,
            key=comparison.key,
            rule_source=rule_source,
            message=comparison.message if comparison.message is not None else "Comparator produced error result.",
            details={"error_code": comparison.error_code, "message": comparison.message},
        )

    if comparison.delta is None or comparison.current_value is None:
        return _error_result(
            family=comparison.family,
            path=comparison.path,
            metric_id=comparison.metric_id,
            key=comparison.key,
            rule_source=rule_source,
            message="Comparator result is missing numeric fields.",
        )

    if rule.strict_key_set is not None:
        return _error_result(
            family=comparison.family,
            path=comparison.path,
            metric_id=comparison.metric_id,
            key=comparison.key,
            rule_source=rule_source,
            message="strict_key_set applies to metric group evaluation only.",
        )

    checks: list[tuple[str, bool, dict[str, object] | None]] = []
    if rule.require_exact_match is True:
        checks.append(
            (
                "require_exact_match",
                comparison.delta == 0.0,
                {"delta": comparison.delta},
            )
        )

    if rule.max_abs_delta is not None:
        checks.append(
            (
                "max_abs_delta",
                abs(comparison.delta) <= rule.max_abs_delta,
                {"delta": comparison.delta, "max_abs_delta": rule.max_abs_delta},
            )
        )

    if rule.max_rate_delta is not None:
        if not comparison.is_rate_metric:
            return _error_result(
                family=comparison.family,
                path=comparison.path,
                metric_id=comparison.metric_id,
                key=comparison.key,
                rule_source=rule_source,
                message="max_rate_delta can be applied only to rate metrics.",
            )
        checks.append(
            (
                "max_rate_delta",
                abs(comparison.delta) <= rule.max_rate_delta,
                {"delta": comparison.delta, "max_rate_delta": rule.max_rate_delta},
            )
        )

    if rule.allowed_values is not None:
        checks.append(
            (
                "allowed_values",
                comparison.current_value in rule.allowed_values,
                {"current_value": comparison.current_value, "allowed_values": list(rule.allowed_values)},
            )
        )

    if not checks:
        return ThresholdEvaluationResult(
            status="PASS",
            family=comparison.family,
            path=comparison.path,
            metric_id=comparison.metric_id,
            key=comparison.key,
            rule_source=rule_source,
            rule_form=None,
            message="No evaluable threshold forms configured.",
        )

    failing = [entry for entry in checks if not entry[1]]
    if failing:
        first = failing[0]
        return ThresholdEvaluationResult(
            status="FAIL",
            family=comparison.family,
            path=comparison.path,
            metric_id=comparison.metric_id,
            key=comparison.key,
            rule_source=rule_source,
            rule_form=first[0],
            message="Threshold check failed.",
            details=first[2],
        )

    return ThresholdEvaluationResult(
        status="PASS",
        family=comparison.family,
        path=comparison.path,
        metric_id=comparison.metric_id,
        key=comparison.key,
        rule_source=rule_source,
        rule_form=checks[0][0],
        message="Threshold check passed.",
    )


def _evaluate_group_rule(
    group_result: MetricGroupComparisonResult,
    config: ThresholdConfig,
) -> ThresholdEvaluationResult | None:
    rule: ThresholdRuleDefinition | None = None
    source: Literal["per-key", "per-path", "metric-family", "global", "none"] = "none"
    if group_result.path in config.per_path:
        rule = config.per_path[group_result.path]
        source = "per-path"
    elif group_result.family in config.metric_family:
        rule = config.metric_family[group_result.family]
        source = "metric-family"
    elif config.global_rule is not None:
        rule = config.global_rule
        source = "global"

    if rule is None or rule.strict_key_set is None:
        return None

    expected = tuple(sorted(rule.strict_key_set))
    current = tuple(sorted(group_result.current_keys))
    if expected != current:
        return ThresholdEvaluationResult(
            status="FAIL",
            family=group_result.family,
            path=group_result.path,
            metric_id=group_result.metric_id,
            key=None,
            rule_source=source,
            rule_form="strict_key_set",
            message="Metric group key set mismatch.",
            details={"expected_keys": list(expected), "current_keys": list(current)},
        )

    return ThresholdEvaluationResult(
        status="PASS",
        family=group_result.family,
        path=group_result.path,
        metric_id=group_result.metric_id,
        key=None,
        rule_source=source,
        rule_form="strict_key_set",
        message="Metric group key set matched.",
    )


def evaluate_thresholds(
    comparison_output: MetricComparisonOutput,
    config: ThresholdConfig,
) -> list[ThresholdEvaluationResult]:
    """Evaluate thresholds deterministically with locked precedence."""
    results: list[ThresholdEvaluationResult] = []

    for item in comparison_output.metric_results:
        rule, source = _select_rule(item, config)
        if rule is None:
            if item.status == "ERROR":
                results.append(
                    _error_result(
                        family=item.family,
                        path=item.path,
                        metric_id=item.metric_id,
                        key=item.key,
                        rule_source="none",
                        message=(
                            item.message if item.message is not None
                            else "Comparator produced error result with no threshold rule."
                        ),
                        details={"error_code": item.error_code, "message": item.message},
                    )
                )
                continue
            results.append(
                ThresholdEvaluationResult(
                    status="PASS",
                    family=item.family,
                    path=item.path,
                    metric_id=item.metric_id,
                    key=item.key,
                    rule_source="none",
                    rule_form=None,
                    message="No threshold rule matched.",
                )
            )
            continue
        results.append(_evaluate_rule(item, rule, source))

    for group_item in comparison_output.group_results:
        group_eval = _evaluate_group_rule(group_item, config)
        if group_eval is not None:
            results.append(group_eval)

    return sorted(results, key=lambda item: (item.family.value, item.path, item.metric_id, item.key or ""))
