"""Regression internal data types for Sentinel testkit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class SuiteCaseDefinition:
    case_id: str
    prompt: str
    schema: str
    provider: str
    model: str
    timeout: int
    contract_version: str = "v1"
    ignore_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SuiteDefinition:
    command: str
    suite_path: str
    cases: list[SuiteCaseDefinition]


@dataclass(frozen=True, slots=True)
class DiffEntry:
    record_type: Literal["missing", "extra", "mismatch"]
    path: str
    expected: object | None = None
    actual: object | None = None


@dataclass(slots=True)
class RunCaseResult:
    case_id: str
    status: Literal["PASS", "DIFF", "ERROR"]
    diffs: list[DiffEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RunSummary:
    total: int
    pass_count: int
    diff_count: int
    error_count: int


@dataclass(frozen=True, slots=True)
class RunSuiteResult:
    command: str
    suite_path: str
    summary: RunSummary
    cases: list[RunCaseResult]


@dataclass(slots=True)
class UpdateCaseResult:
    case_id: str
    status: Literal["UPDATED", "ERROR"]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class UpdateSummary:
    total: int
    updated: int
    errors: int


@dataclass(frozen=True, slots=True)
class UpdateSuiteResult:
    command: str
    suite_path: str
    summary: UpdateSummary
    cases: list[UpdateCaseResult]

