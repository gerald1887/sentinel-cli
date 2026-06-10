from __future__ import annotations

from .hashing import HashingError, recompute_hashes_for_record
from .types import AuditRecord, AuditVerifyRecordResult, AuditVerifyResult, AuditVerifyResultSummary


class VerifyError(Exception):
    pass


def verify_records(records: list[AuditRecord]) -> AuditVerifyResult:
    total = len(records)
    valid = 0
    invalid = 0
    results: list[AuditVerifyRecordResult] = []

    for record in records:
        try:
            expected = record.hashes
            if not all(
                expected_field
                for expected_field in (
                    expected.input_hash,
                    expected.config_hash,
                    expected.result_hash,
                    expected.full_hash,
                )
            ):
                results.append(
                    AuditVerifyRecordResult(
                        audit_id=record.audit_id,
                        status="ERROR",
                        message="missing stored hash value",
                    )
                )
                invalid += 1
                continue

            recomputed = recompute_hashes_for_record(record)
        except HashingError as exc:
            results.append(
                AuditVerifyRecordResult(
                    audit_id=record.audit_id,
                    status="ERROR",
                    message=str(exc),
                )
            )
            invalid += 1
            continue

        if (
            recomputed.input_hash == expected.input_hash
            and recomputed.config_hash == expected.config_hash
            and recomputed.result_hash == expected.result_hash
            and recomputed.full_hash == expected.full_hash
        ):
            results.append(
                AuditVerifyRecordResult(
                    audit_id=record.audit_id,
                    status="PASS",
                    message="integrity verified",
                )
            )
            valid += 1
        else:
            results.append(
                AuditVerifyRecordResult(
                    audit_id=record.audit_id,
                    status="FAIL",
                    message="hash mismatch",
                )
            )
            invalid += 1

    summary = AuditVerifyResultSummary(
        total_records=total,
        valid=valid,
        invalid=invalid,
    )
    return AuditVerifyResult(summary=summary, records=results, selection={})

