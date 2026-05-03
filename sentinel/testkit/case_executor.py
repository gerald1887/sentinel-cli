"""Regression bridge from suite case definition to Contract execution."""

from __future__ import annotations

from sentinel.core.errors import INTERNAL_ERROR, SentinelError
from sentinel.core.runner import run_contract
from sentinel.testkit.types import SuiteCaseDefinition


def execute_case(case: SuiteCaseDefinition) -> object | SentinelError:
    """Execute one suite case via Contract runner and return approved output."""
    result = run_contract(
        prompt_path=case.prompt,
        schema_path=case.schema,
        provider=case.provider,
        model=case.model,
        timeout=case.timeout,
    )

    if result.status in ("FAIL", "ERROR"):
        if result.error is not None:
            return result.error
        return SentinelError(
            category=INTERNAL_ERROR,
            code="SENTINEL_CASE_EXECUTION_ERROR",
            message="Case execution failed without structured error.",
            details={"case_id": case.case_id, "status": result.status},
        )

    approved_output = getattr(result, "approved_output", None)
    if approved_output is None:
        return SentinelError(
            category=INTERNAL_ERROR,
            code="SENTINEL_CASE_EXECUTION_MISSING_OUTPUT",
            message="Case execution returned PASS but no approved output.",
            details={"case_id": case.case_id},
        )
    return approved_output

