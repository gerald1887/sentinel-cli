from __future__ import annotations

from pathlib import Path

from sentinel.audit.store import AuditStoreError, append_record, read_records
from sentinel.audit.types import AuditConfigs, AuditHashes, AuditInputRefs, AuditRecord


def _make_record(audit_id: str) -> AuditRecord:
    return AuditRecord(
        audit_version="1",
        audit_id=audit_id,
        timestamp_utc="2024-01-01T00:00:00Z",
        command="audit record",
        execution_id="exec",
        input_refs=AuditInputRefs(
            prompt_file=None,
            schema_file=None,
            suite_file=None,
            assertions_file=None,
            signals_file=None,
            rules_file=None,
        ),
        configs=AuditConfigs(schema=None, assertions=None, signals=None, rules=None),
        result={},
        event_ids=[],
        hashes=AuditHashes(input_hash="i", config_hash="c", result_hash="r", full_hash="f"),
        metadata=None,
    )


def test_append_and_read_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    record = _make_record("a1")
    append_record(str(path), record)

    loaded = list(read_records(str(path)))
    assert len(loaded) == 1
    assert loaded[0].audit_id == "a1"


def test_partial_line_is_error(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    with path.open("w", encoding="utf-8") as f:
        f.write('{"incomplete": true}')

    try:
        list(read_records(str(path)))
        raised = False
    except AuditStoreError:
        raised = True

    assert raised

