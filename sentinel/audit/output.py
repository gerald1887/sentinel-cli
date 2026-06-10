from __future__ import annotations

from collections.abc import Iterable

from .types import AuditReplayResult, AuditVerifyResult


def render_verify(result: AuditVerifyResult) -> list[str]:
    lines: list[str] = [
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


def render_replay(results: Iterable[AuditReplayResult]) -> list[str]:
    results_list = list(results)
    total = len(results_list)
    passed = sum(1 for r in results_list if r.status == "PASS")
    failed = sum(1 for r in results_list if r.status == "FAIL")
    errors = sum(1 for r in results_list if r.status == "ERROR")

    lines: list[str] = [
        f"AUDIT REPLAY SUMMARY total={total} pass={passed} fail={failed} error={errors}",
    ]
    for r in results_list:
        if r.status == "FAIL":
            lines.append(f"AUDIT FAIL {r.audit_id} mismatch")
        elif r.status == "ERROR":
            lines.append(f"AUDIT ERROR {r.audit_id} {r.message}")
    return lines

