from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class AuditInputRefs:
    prompt_file: Optional[str]
    schema_file: Optional[str]
    suite_file: Optional[str]
    assertions_file: Optional[str]
    signals_file: Optional[str]
    rules_file: Optional[str]


@dataclass(frozen=True)
class AuditConfigs:
    schema: Optional[Dict[str, Any]]
    assertions: Optional[Any]
    signals: Optional[Any]
    rules: Optional[Any]


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
    result: Dict[str, Any]
    event_ids: List[str]
    hashes: AuditHashes
    metadata: Optional[Dict[str, Any]]


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
    records: List[AuditVerifyRecordResult]
    selection: Dict[str, Any]


@dataclass(frozen=True)
class AuditReplayResult:
    audit_id: str
    status: str
    expected_hash: Optional[str]
    actual_hash: Optional[str]
    message: str

