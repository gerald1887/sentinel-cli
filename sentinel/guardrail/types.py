"""Guard guardrail result types for Sentinel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict


GuardCheckSummary = TypedDict(
    "GuardCheckSummary",
    {"total": int, "pass": int, "fail": int, "error": int},
)


@dataclass(frozen=True, slots=True)
class GuardAssertionResult:
    id: str
    status: Literal["PASS", "FAIL"]
    type: str
    path: str
    expected: object | None
    actual: object | None
    message: str


@dataclass(frozen=True, slots=True)
class GuardCheckResult:
    status: Literal["PASS", "FAIL", "ERROR"]
    summary: GuardCheckSummary
    assertions: list[GuardAssertionResult]

