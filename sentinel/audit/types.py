from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AuditInputRefs:
    prompt_file: str | None
    schema_file: str | None
    suite_file: str | None
    assertions_file: str | None
    signals_file: str | None
    rules_file: str | None


@dataclass(frozen=True)
class AuditConfigs:
    schema: dict[str, Any] | None
    assertions: Any | None
    signals: Any | None
    rules: Any | None


@dataclass(frozen=True)
class AuditHashes:
    input_hash: str
    config_hash: str
    result_hash: str
    full_hash: str


@dataclass(frozen=True)
class AuditRecord:
    audit_version: str
    audit_id: str
    timestamp_utc: str
    command: str
    execution_id: str
    input_refs: AuditInputRefs
    configs: AuditConfigs
    result: dict[str, Any]
    event_ids: list[str]
    hashes: AuditHashes
    metadata: dict[str, Any] | None


@dataclass(frozen=True)
class AuditVerifyRecordResult:
    audit_id: str
    status: str
    message: str


@dataclass(frozen=True)
class AuditVerifyResultSummary:
    total_records: int
    valid: int
    invalid: int


@dataclass(frozen=True)
class AuditVerifyResult:
    summary: AuditVerifyResultSummary
    records: list[AuditVerifyRecordResult]
    selection: dict[str, Any]


@dataclass(frozen=True)
class AuditReplayResult:
    audit_id: str
    status: str
    expected_hash: str | None
    actual_hash: str | None
    message: str

