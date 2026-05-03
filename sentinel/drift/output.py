"""Deterministic text rendering for Drift drift results."""

from __future__ import annotations

from sentinel.drift.runner import DriftBaselineRunResult, DriftCheckRunResult


def _metric_name(metric_id: str, key: str | None) -> str:
    if key is None:
        return metric_id
    return f"{metric_id}.{key}"


def _threshold_value(details: dict[str, object] | None) -> str:
    if not details:
        return "-"
    for name in ("max_abs_delta", "max_rate_delta", "allowed_values", "require_exact_match", "strict_key_set"):
        if name in details:
            return str(details[name])
    return "-"


def _comparison_lookup(result: DriftCheckRunResult) -> dict[tuple[str, str, str, str | None], tuple[float | None, float | None, float | None]]:
    out: dict[tuple[str, str, str, str | None], tuple[float | None, float | None, float | None]] = {}
    for item in result.comparisons:
        out[(item.family.value, item.path, item.metric_id, item.key)] = (
            item.baseline_value,
            item.current_value,
            item.delta,
        )
    return out


def render_drift_baseline(result: DriftBaselineRunResult) -> list[str]:
    """Render baseline result as deterministic summary-only output."""
    summary = result.summary
    return [
        "DRIFT BASELINE SUMMARY "
        f"total_cases={summary.total_cases} "
        f"approved={summary.approved_cases} "
        f"errors={summary.error_cases} "
        f"metrics={summary.metrics}"
    ]


def render_drift_check(result: DriftCheckRunResult) -> list[str]:
    """Render drift check summary first, then only FAIL/ERROR findings."""
    comparison_map = _comparison_lookup(result)

    lines = [
        "DRIFT SUMMARY "
        f"total_metrics={result.summary.total_findings} "
        f"pass={result.summary.passed} "
        f"fail={result.summary.failed} "
        f"error={result.summary.errors} "
        f"cases={result.summary.total_cases} "
        f"approved={result.summary.approved_cases}"
    ]
    for finding in result.evaluations:
        if finding.status not in {"FAIL", "ERROR"}:
            continue
        group = finding.family.value
        metric_name = _metric_name(finding.metric_id, finding.key)
        if finding.status == "ERROR":
            lines.append(f"METRIC ERROR {group} {finding.path} {metric_name} {finding.message}")
            continue

        baseline, current, delta = comparison_map.get(
            (finding.family.value, finding.path, finding.metric_id, finding.key),
            (None, None, None),
        )
        threshold = _threshold_value(finding.details)
        lines.append(
            f"METRIC FAIL {group} {finding.path} {metric_name} "
            f"baseline={baseline} current={current} delta={delta} threshold={threshold}"
        )
    return lines
