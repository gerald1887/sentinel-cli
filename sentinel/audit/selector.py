from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sentinel.core.errors import SCHEMA_INVALID, SentinelError

from .types import AuditRecord


@dataclass(frozen=True)
class SelectionFilters:
    from_ts: str | None = None
    to_ts: str | None = None
    command: str | None = None
    provider: str | None = None
    model: str | None = None
    event_type: str | None = None
    case_id: str | None = None
    status: str | None = None
    audit_id: str | None = None
    last: int | None = None


def validate_selection_filters(filters: SelectionFilters) -> SentinelError | None:
    """Validate audit selection filter values.

    Mirrors the monitor selector's validation: ISO-8601 UTC timestamps,
    from <= to ordering, and last >= 1.
    """
    for label, value in (
        ("from", filters.from_ts),
        ("to", filters.to_ts),
    ):
        if value is None:
            continue
        if not _is_iso8601_utc(value):
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_AUDIT_INVALID_FILTER",
                message=f"Filter '--{label}' must be ISO-8601 UTC format ending with 'Z'.",
            )

    if filters.from_ts is not None and filters.to_ts is not None:
        if filters.from_ts > filters.to_ts:
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_AUDIT_INVALID_FILTER",
                message="Filter '--from' must be less than or equal to '--to'.",
            )

    if filters.last is not None and filters.last < 1:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_AUDIT_INVALID_FILTER",
            message="Filter '--last' must be >= 1.",
        )
    return None


def apply_filters(records: Iterable[AuditRecord], filters: SelectionFilters) -> list[AuditRecord] | SentinelError:
    filter_error = validate_selection_filters(filters)
    if filter_error is not None:
        return filter_error

    # Preserve file order; no sorting.
    selected: list[AuditRecord] = list(records)

    # 1. from/to (inclusive, ISO-8601 string comparison).
    if filters.from_ts is not None:
        selected = [r for r in selected if r.timestamp_utc >= filters.from_ts]
    if filters.to_ts is not None:
        selected = [r for r in selected if r.timestamp_utc <= filters.to_ts]

    # 2. command
    if filters.command is not None:
        selected = [r for r in selected if r.command == filters.command]

    # 3. provider
    if filters.provider is not None:
        selected = [
            r
            for r in selected
            if r.result.get("provider") == filters.provider
        ]

    # 4. model
    if filters.model is not None:
        selected = [
            r
            for r in selected
            if r.result.get("model") == filters.model
        ]

    # 5. event_type
    if filters.event_type is not None:
        selected = [
            r
            for r in selected
            if r.result.get("event_type") == filters.event_type
        ]

    # 6. case_id
    if filters.case_id is not None:
        selected = [
            r
            for r in selected
            if r.result.get("case_id") == filters.case_id
        ]

    # 7. status
    if filters.status is not None:
        selected = [
            r
            for r in selected
            if r.result.get("status") == filters.status
        ]

    # 8. audit_id
    if filters.audit_id is not None:
        selected = [r for r in selected if r.audit_id == filters.audit_id]

    # last-N after all filters.
    if filters.last is not None and filters.last > 0:
        if len(selected) > filters.last:
            selected = selected[-filters.last :]

    return selected


def _is_iso8601_utc(value: str) -> bool:
    if len(value) < 20:
        return False
    return "T" in value and value.endswith("Z")
