"""Unit tests for Guard guardrail result types."""

from __future__ import annotations

from sentinel.guardrail.types import (
    GuardAssertionResult,
    GuardCheckResult,
    GuardCheckSummary,
)


def test_guard_guard_types_instantiation_and_summary_storage() -> None:
    summary = GuardCheckSummary(total=2, **{"pass": 1}, fail=1, error=0)
    first = GuardAssertionResult(
        id="a1",
        status="PASS",
        type="contains",
        path="$.output",
        expected="ok",
        actual="ok",
        message="matched",
    )
    second = GuardAssertionResult(
        id="a2",
        status="FAIL",
        type="equals",
        path="$.score",
        expected=10,
        actual=7,
        message="expected 10",
    )

    result = GuardCheckResult(
        status="FAIL",
        summary=summary,
        assertions=[first, second],
    )

    assert result.summary["total"] == 2
    assert result.summary["pass"] == 1
    assert result.summary["fail"] == 1
    assert result.summary["error"] == 0
    assert result.assertions[0].id == "a1"
    assert result.assertions[1].id == "a2"


def test_guard_guard_allowed_status_literals_examples() -> None:
    summary = GuardCheckSummary(total=0, **{"pass": 0}, fail=0, error=0)
    assertion = GuardAssertionResult(
        id="a",
        status="PASS",
        type="exists",
        path="$.x",
        expected=None,
        actual=None,
        message="ok",
    )

    assert GuardCheckResult(status="PASS", summary=summary, assertions=[assertion]).status == "PASS"
    assert GuardCheckResult(status="FAIL", summary=summary, assertions=[assertion]).status == "FAIL"
    assert GuardCheckResult(status="ERROR", summary=summary, assertions=[assertion]).status == "ERROR"

    assert GuardAssertionResult(
        id="b",
        status="PASS",
        type="exists",
        path="$.y",
        expected=None,
        actual=None,
        message="ok",
    ).status == "PASS"
    assert GuardAssertionResult(
        id="c",
        status="FAIL",
        type="equals",
        path="$.z",
        expected=1,
        actual=0,
        message="mismatch",
    ).status == "FAIL"


def test_guard_guard_expected_actual_can_be_none_and_order_preserved() -> None:
    first = GuardAssertionResult(
        id="first",
        status="PASS",
        type="exists",
        path="$.a",
        expected=None,
        actual=None,
        message="ok",
    )
    second = GuardAssertionResult(
        id="second",
        status="FAIL",
        type="equals",
        path="$.b",
        expected=None,
        actual=None,
        message="missing",
    )
    result = GuardCheckResult(
        status="FAIL",
        summary=GuardCheckSummary(total=2, **{"pass": 1}, fail=1, error=0),
        assertions=[first, second],
    )

    assert result.assertions[0].id == "first"
    assert result.assertions[1].id == "second"
    assert result.assertions[0].expected is None
    assert result.assertions[0].actual is None
    assert result.assertions[1].expected is None
    assert result.assertions[1].actual is None

