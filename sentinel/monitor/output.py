"""Deterministic rendering for monitor inspect output."""

from __future__ import annotations

import json
from dataclasses import asdict

from sentinel.monitor.types import Event, MonitorCheckResult, SignalResult


def render_inspect_events(events: list[Event]) -> list[str]:
    """Render selected events as stable JSON lines."""
    return [json.dumps(asdict(event), sort_keys=True, separators=(",", ":")) for event in events]


def render_summary(selected_event_count: int, results: list[SignalResult]) -> list[str]:
    """Render deterministic summary output."""
    lines = [
        "MONITOR SUMMARY",
        f"signals={len(results)} selected_events={selected_event_count}",
    ]
    for result in results:
        lines.append(f"SIGNAL {result.name} value={_render_value(result.value)} events={result.event_count}")
    return lines


def _render_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if value is None:
        return "null"
    return str(value)


def render_check(result: MonitorCheckResult) -> list[str]:
    """Render deterministic check output with summary-first format."""
    summary = result.summary
    lines = [
        "MONITOR CHECK SUMMARY "
        f"total_rules={summary['total_rules']} pass={summary['pass']} fail={summary['fail']} "
        f"error={summary['error']} events={summary['events']}"
    ]
    for rule in result.rules:
        if rule.status == "FAIL":
            lines.append(
                f"RULE FAIL {rule.id} signal={rule.signal} actual={_render_value(rule.actual)} "
                f"operator={rule.operator} expected={_render_value(rule.expected)}"
            )
        elif rule.status == "ERROR":
            lines.append(f"RULE ERROR {rule.id} {rule.message}")
    return lines
