from __future__ import annotations

from sentinel.audit.types import (
    AuditConfigs,
    AuditHashes,
    AuditInputRefs,
    AuditRecord,
    AuditVerifyRecordResult,
)
from sentinel.audit.verify_engine import verify_records


def _record_with_hashes(audit_id: str, hashes: AuditHashes) -> AuditRecord:
    return AuditRecord(
        audit_version="1",
        audit_id=audit_id,
        timestamp_utc="2024-01-01T00:00:00Z",
        command="audit record",
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
        result={},
        event_ids=[],
        hashes=hashes,
        metadata=None,
    )


def test_verify_pass_and_fail_and_error_summary() -> None:
    # PASS record: use hashes recomputed by the engine to ensure it verifies.
    base = _record_with_hashes(
        "ok",
        AuditHashes(input_hash="i", config_hash="c", result_hash="r", full_hash="f"),
    )
    from sentinel.audit.hashing import recompute_hashes_for_record

    ok_hashes = recompute_hashes_for_record(base)
    pass_record = _record_with_hashes("ok", ok_hashes)

    # FAIL record: only result_hash differs.
    fail_hashes = AuditHashes(
        input_hash=ok_hashes.input_hash,
        config_hash=ok_hashes.config_hash,
        result_hash="different",
        full_hash=ok_hashes.full_hash,
    )
    fail_record = _record_with_hashes("fail", fail_hashes)

    # ERROR record: missing full_hash value.
    error_hashes = AuditHashes(
        input_hash=ok_hashes.input_hash,
        config_hash=ok_hashes.config_hash,
        result_hash=ok_hashes.result_hash,
        full_hash="",
    )
    error_record = _record_with_hashes("err", error_hashes)

    result = verify_records([pass_record, fail_record, error_record])

    assert result.summary.total_records == 3
    assert result.summary.valid == 1
    assert result.summary.invalid == 2

    by_id: dict[str, AuditVerifyRecordResult] = {r.audit_id: r for r in result.records}
    assert by_id["ok"].status == "PASS"
    assert by_id["fail"].status == "FAIL"
    assert by_id["err"].status == "ERROR"

