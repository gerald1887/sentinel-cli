from __future__ import annotations

from dataclasses import asdict

from sentinel.core.errors import (
    EXIT_CONTRACT_FAIL,
    EXIT_ERROR,
    EXIT_PASS,
    INTERNAL_ERROR,
    SentinelError,
)

from .builder import AuditBuilderError, build_audit_record_from_result
from .output import render_replay, render_verify
from .replay_engine import replay_record
from .selector import SelectionFilters, apply_filters
from .store import AuditStoreError, append_record, read_records
from .types import AuditRecord, AuditReplayResult
from .verify_engine import verify_records


def run_audit_record(
    *,
    audit_file: str,
    source: str,
    events: str | None,
) -> tuple[int, list[str]]:
    try:
        record = build_audit_record_from_result(
            command=None,
            execution_id=None,
            result_path=source,
            prompt_file=None,
            schema_file=None,
            suite_file=None,
            assertions_file=None,
            signals_file=None,
            rules_file=None,
            events_file=events,
        )
    except AuditBuilderError as exc:
        return EXIT_ERROR, [f"AUDIT RECORD ERROR {exc}"]

    try:
        append_record(audit_file, record)
    except AuditStoreError as exc:
        return EXIT_ERROR, [f"AUDIT RECORD ERROR {exc}"]

    return EXIT_PASS, []


def _load_all_records(audit_file: str) -> list[AuditRecord] | SentinelError:
    try:
        records = list(read_records(audit_file))
    except AuditStoreError as exc:
        return SentinelError(
            category=INTERNAL_ERROR,
            code="SENTINEL_AUDIT_STORE_ERROR",
            message=str(exc),
            location=audit_file,
        )
    return records


def run_audit_inspect(audit_file: str, filters: SelectionFilters) -> tuple[int, list[str]]:
    loaded = _load_all_records(audit_file)
    if isinstance(loaded, SentinelError):
        return EXIT_ERROR, [
            "AUDIT INSPECT ERROR",
            f"{loaded.category} {loaded.code} {loaded.message}",
        ]

    selected = apply_filters(loaded, filters)
    if isinstance(selected, SentinelError):
        return EXIT_ERROR, [
            "AUDIT INSPECT ERROR",
            f"{selected.category} {selected.code} {selected.message}",
        ]
    # Deterministic JSON output per record.
    lines = [json_dumps(asdict(record)) for record in selected]
    return EXIT_PASS, lines


def run_audit_verify(audit_file: str, filters: SelectionFilters) -> tuple[int, list[str]]:
    loaded = _load_all_records(audit_file)
    if isinstance(loaded, SentinelError):
        return EXIT_ERROR, [
            "AUDIT VERIFY ERROR",
            f"{loaded.category} {loaded.code} {loaded.message}",
        ]

    selected = apply_filters(loaded, filters)
    if isinstance(selected, SentinelError):
        return EXIT_ERROR, [
            "AUDIT VERIFY ERROR",
            f"{selected.category} {selected.code} {selected.message}",
        ]
    verify_result = verify_records(selected)
    lines = render_verify(verify_result)

    # Exit code semantics: any FAIL or ERROR → EXIT_ERROR (2); else PASS (0).
    has_fail_or_error = any(
        r.status in ("FAIL", "ERROR") for r in verify_result.records
    )
    return (EXIT_ERROR if has_fail_or_error else EXIT_PASS), lines


def run_audit_replay(audit_file: str, audit_id: str) -> tuple[int, list[str]]:
    loaded = _load_all_records(audit_file)
    if isinstance(loaded, SentinelError):
        return EXIT_ERROR, [
            "AUDIT REPLAY ERROR",
            f"{loaded.category} {loaded.code} {loaded.message}",
        ]

    target: AuditRecord | None = None
    for record in loaded:
        if record.audit_id == audit_id:
            target = record
            break

    if target is None:
        return EXIT_ERROR, [f"AUDIT ERROR {audit_id} audit_id not found"]

    replay_result: AuditReplayResult = replay_record(target)
    lines = render_replay([replay_result])

    if replay_result.status == "PASS":
        return EXIT_PASS, lines
    if replay_result.status == "FAIL":
        return EXIT_CONTRACT_FAIL, lines
    return EXIT_ERROR, lines


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"))

