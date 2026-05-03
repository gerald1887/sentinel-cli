"""Unit tests for Regression case execution bridge."""

from __future__ import annotations

from dataclasses import dataclass

from sentinel.core.errors import SentinelError
from sentinel.testkit.case_executor import execute_case
from sentinel.testkit.types import SuiteCaseDefinition


@dataclass
class _FakeResult:
    status: str
    error: SentinelError | None = None
    approved_output: object | None = None


def _case() -> SuiteCaseDefinition:
    return SuiteCaseDefinition(
        case_id="case-1",
        prompt="prompt.txt",
        schema="schema.json",
        provider="openai",
        model="gpt-4.1",
        timeout=17,
    )


def test_execute_case_success_returns_approved_output(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.case_executor.run_contract",
        lambda **kwargs: _FakeResult(status="PASS", approved_output={"ok": True}),
    )

    result = execute_case(_case())
    assert result == {"ok": True}


def test_execute_case_contract_failure_returns_structured_error(monkeypatch) -> None:
    err = SentinelError(
        category="JSON_PARSE_ERROR",
        code="SENTINEL_JSON_PARSE_ERROR",
        message="invalid json",
    )
    monkeypatch.setattr(
        "sentinel.testkit.case_executor.run_contract",
        lambda **kwargs: _FakeResult(status="FAIL", error=err),
    )

    result = execute_case(_case())
    assert isinstance(result, SentinelError)
    assert result is err


def test_execute_case_execution_error_returns_structured_error(monkeypatch) -> None:
    err = SentinelError(
        category="PROVIDER_TIMEOUT",
        code="SENTINEL_PROVIDER_TIMEOUT",
        message="timed out",
    )
    monkeypatch.setattr(
        "sentinel.testkit.case_executor.run_contract",
        lambda **kwargs: _FakeResult(status="ERROR", error=err),
    )

    result = execute_case(_case())
    assert isinstance(result, SentinelError)
    assert result is err


def test_execute_case_pass_without_output_returns_internal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.case_executor.run_contract",
        lambda **kwargs: _FakeResult(status="PASS", approved_output=None),
    )

    result = execute_case(_case())
    assert isinstance(result, SentinelError)
    assert result.category == "INTERNAL_ERROR"
    assert result.code == "SENTINEL_CASE_EXECUTION_MISSING_OUTPUT"


def test_execute_case_fail_without_error_returns_internal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.case_executor.run_contract",
        lambda **kwargs: _FakeResult(status="FAIL", error=None),
    )

    result = execute_case(_case())
    assert isinstance(result, SentinelError)
    assert result.category == "INTERNAL_ERROR"
    assert result.code == "SENTINEL_CASE_EXECUTION_ERROR"


def test_execute_case_error_without_error_returns_internal_error(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.case_executor.run_contract",
        lambda **kwargs: _FakeResult(status="ERROR", error=None),
    )

    result = execute_case(_case())
    assert isinstance(result, SentinelError)
    assert result.category == "INTERNAL_ERROR"
    assert result.code == "SENTINEL_CASE_EXECUTION_ERROR"


def test_execute_case_passes_correct_case_fields_to_runner(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_run_contract(**kwargs):
        captured.update(kwargs)
        return _FakeResult(status="PASS", approved_output={"ok": True})

    monkeypatch.setattr("sentinel.testkit.case_executor.run_contract", _fake_run_contract)

    execute_case(_case())

    assert captured == {
        "prompt_path": "prompt.txt",
        "schema_path": "schema.json",
        "provider": "openai",
        "model": "gpt-4.1",
        "timeout": 17,
    }

