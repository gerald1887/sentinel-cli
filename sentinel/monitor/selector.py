"""Deterministic event selector for monitor inspect."""

from __future__ import annotations

from dataclasses import dataclass

from sentinel.core.errors import SCHEMA_INVALID, SentinelError
from sentinel.monitor.types import Event


@dataclass(frozen=True, slots=True)
class InspectFilters:
    """Supported monitor inspect filters."""

    from_timestamp_utc: str | None = None
    to_timestamp_utc: str | None = None
    last: int | None = None
    command: str | None = None
    provider: str | None = None
    model: str | None = None
    event_type: str | None = None
    case_id: str | None = None
    status: str | None = None


def select_events(events: list[Event], filters: InspectFilters) -> list[Event] | SentinelError:
    """Apply inspect filters in fixed deterministic order."""
    filter_error = validate_inspect_filters(filters)
    if filter_error is not None:
        return filter_error

    selected = events
    selected = _filter_time_range(selected, filters.from_timestamp_utc, filters.to_timestamp_utc)
    selected = _filter_equals(selected, "command", filters.command)
    selected = _filter_equals(selected, "provider", filters.provider)
    selected = _filter_equals(selected, "model", filters.model)
    selected = _filter_equals(selected, "event_type", filters.event_type)
    selected = _filter_equals(selected, "suite_case_id", filters.case_id)
    selected = _filter_equals(selected, "status", filters.status)

    if filters.last is not None:
        selected = selected[-filters.last :]
    return selected


def validate_inspect_filters(filters: InspectFilters) -> SentinelError | None:
    """Validate inspect filter values."""
    for label, value in (
        ("from", filters.from_timestamp_utc),
        ("to", filters.to_timestamp_utc),
    ):
        if value is None:
            continue
        if not _is_iso8601_utc(value):
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_MONITOR_INVALID_FILTER",
                message=f"Filter '--{label}' must be ISO-8601 UTC format ending with 'Z'.",
            )

    if filters.from_timestamp_utc is not None and filters.to_timestamp_utc is not None:
        if filters.from_timestamp_utc > filters.to_timestamp_utc:
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_MONITOR_INVALID_FILTER",
                message="Filter '--from' must be less than or equal to '--to'.",
            )

    if filters.last is not None and filters.last < 1:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_MONITOR_INVALID_FILTER",
            message="Filter '--last' must be >= 1.",
        )
    return None


def _filter_time_range(events: list[Event], from_ts: str | None, to_ts: str | None) -> list[Event]:
    selected = events
    if from_ts is not None:
        selected = [event for event in selected if event.timestamp_utc >= from_ts]
    if to_ts is not None:
        selected = [event for event in selected if event.timestamp_utc <= to_ts]
    return selected


def _filter_equals(events: list[Event], field_name: str, expected: str | None) -> list[Event]:
    if expected is None:
        return events
    return [event for event in events if getattr(event, field_name) == expected]


def _is_iso8601_utc(value: str) -> bool:
    # integration milestone uses string-ordered UTC timestamp filtering.
    if len(value) < 20:
        return False
    return "T" in value and value.endswith("Z")
