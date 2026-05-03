from __future__ import annotations

from typing import Iterable, List

from .types import AuditReplayResult, AuditVerifyRecordResult, AuditVerifyResult


def render_verify(result: AuditVerifyResult) -> List[str]:
    lines: List[str] = [
        "AUDIT VERIFY SUMMARY "
        f"total_records={result.summary.total_records} "
        f"valid={result.summary.valid} invalid={result.summary.invalid}"
    ]
    for record in result.records:
        if record.status == "FAIL":
            lines.append(f"AUDIT FAIL {record.audit_id} {record.message}")
        # Record-level ERROR states are intentionally not rendered to match the
        # Audit verify output contract, which only exposes FAIL lines
        # following the summary.
    return lines


def render_replay(results: Iterable[AuditReplayResult]) -> List[str]:
    results_list = list(results)
    total = len(results_list)
    passed = sum(1 for r in results_list if r.status == "PASS")
    failed = sum(1 for r in results_list if r.status == "FAIL")
    errors = sum(1 for r in results_list if r.status == "ERROR")

    lines: List[str] = [
        f"AUDIT REPLAY SUMMARY total={total} pass={passed} fail={failed} error={errors}",
    ]
    for r in results_list:
        if r.status == "FAIL":
            lines.append(f"AUDIT FAIL {r.audit_id} mismatch")
        elif r.status == "ERROR":
            lines.append(f"AUDIT ERROR {r.audit_id} {r.message}")
    return lines

