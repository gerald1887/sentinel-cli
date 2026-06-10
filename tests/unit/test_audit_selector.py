from __future__ import annotations

from sentinel.audit.selector import SelectionFilters, apply_filters
from sentinel.audit.types import AuditConfigs, AuditHashes, AuditInputRefs, AuditRecord


def _make_record(audit_id: str, timestamp: str, command: str, status: str) -> AuditRecord:
    return AuditRecord(
        audit_version="1",
        audit_id=audit_id,
        timestamp_utc=timestamp,
        command=command,
        execution_id="e",
        input_refs=AuditInputRefs(
            prompt_file=None,
            schema_file=None,
            suite_file=None,
            assertions_file=None,
            signals_file=None,
            rules_file=None,
        ),
        configs=AuditConfigs(schema=None, assertions=None, signals=None, rules=None),
        result={"status": status},
        event_ids=[],
        hashes=AuditHashes(input_hash="i", config_hash="c", result_hash="r", full_hash="f"),
        metadata=None,
    )


def test_selector_applies_filters_in_fixed_order() -> None:
    records = [
        _make_record("a1", "2024-01-01T00:00:00Z", "audit record", "PASS"),
        _make_record("a2", "2024-01-02T00:00:00Z", "audit record", "FAIL"),
        _make_record("a3", "2024-01-03T00:00:00Z", "other", "PASS"),
    ]

    filters = SelectionFilters(
        from_ts="2024-01-02T00:00:00Z",
        to_ts="2024-01-03T00:00:00Z",
        command="audit record",
        status="FAIL",
        last=None,
    )

    selected = apply_filters(records, filters)

    assert [r.audit_id for r in selected] == ["a2"]

