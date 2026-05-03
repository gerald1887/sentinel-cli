from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .types import AuditRecord


@dataclass(frozen=True)
class SelectionFilters:
    from_ts: Optional[str] = None
    to_ts: Optional[str] = None
    command: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    event_type: Optional[str] = None
    case_id: Optional[str] = None
    status: Optional[str] = None
    audit_id: Optional[str] = None
    last: Optional[int] = None


def apply_filters(records: Iterable[AuditRecord], filters: SelectionFilters) -> List[AuditRecord]:
    # Preserve file order; no sorting.
    selected: List[AuditRecord] = list(records)

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

