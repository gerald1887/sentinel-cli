"""Minimal smoke tests for sentinel.core.runner provider-boundary behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel.core.errors import JSON_PARSE_ERROR, SCHEMA_INVALID, SentinelError
from sentinel.core.runner import run_contract
from sentinel.providers.base import (
    PROVIDER_NETWORK_ERROR,
    ProviderRequest,
    ProviderResponseNormalized,
)


def _write_prompt_and_schema(tmp_path: Path, schema_obj: dict) -> tuple[str, str]:
    prompt_file = tmp_path / "prompt.txt"
    schema_file = tmp_path / "schema.json"
    prompt_file.write_text("Return a JSON object.", encoding="utf-8")
    schema_file.write_text(json.dumps(schema_obj), encoding="utf-8")
    return str(prompt_file), str(schema_file)


def test_run_contract_unknown_provider_returns_error(tmp_path: Path) -> None:
    prompt_path, schema_path = _write_prompt_and_schema(tmp_path, {"type": "object"})

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="unknown-provider",
        model="dummy-model",
        timeout=5,
    )

    assert result.status == "ERROR"
    assert result.error is not None
    assert result.error.category == "PROVIDER_UNKNOWN_ERROR"


def test_run_contract_openai_stub_with_permissive_schema_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_path, schema_path = _write_prompt_and_schema(tmp_path, {"type": "object"})

    class _FakeAdapter:
        def invoke(self, request: ProviderRequest) -> ProviderResponseNormalized:
            _ = request
            return ProviderResponseNormalized(raw_text="{}")

    monkeypatch.setattr(
        "sentinel.core.runner.get_provider_adapter",
        lambda provider_name: _FakeAdapter(),
    )

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="openai",
        model="gpt-stub",
        timeout=5,
    )

    assert result.status == "PASS"
    assert result.error is None


def test_run_contract_openai_stub_with_mismatch_schema_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_path, schema_path = _write_prompt_and_schema(
        tmp_path,
        {
            "type": "object",
            "properties": {"required_key": {"type": "string"}},
            "required": ["required_key"],
        },
    )

    class _FakeAdapter:
        def invoke(self, request: ProviderRequest) -> ProviderResponseNormalized:
            _ = request
            return ProviderResponseNormalized(raw_text="{}")

    monkeypatch.setattr(
        "sentinel.core.runner.get_provider_adapter",
        lambda provider_name: _FakeAdapter(),
    )

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="openai",
        model="gpt-stub",
        timeout=5,
    )

    assert result.status == "FAIL"
    assert result.error is not None


def test_run_contract_adapter_invoke_error_propagates_as_runner_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_path, schema_path = _write_prompt_and_schema(tmp_path, {"type": "object"})

    adapter_error = SentinelError(
        category=PROVIDER_NETWORK_ERROR,
        code="SENTINEL_TEST_ADAPTER_ERROR",
        message="Deterministic adapter failure.",
    )

    class _FakeAdapter:
        def invoke(self, request: ProviderRequest) -> SentinelError:
            _ = request
            return adapter_error

    def _fake_get_provider_adapter(provider_name: str):
        _ = provider_name
        return _FakeAdapter()

    monkeypatch.setattr(
        "sentinel.core.runner.get_provider_adapter",
        _fake_get_provider_adapter,
    )

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="any-name",
        model="gpt-stub",
        timeout=5,
    )

    assert result.status == "ERROR"
    assert result.error is not None
    assert result.error.category == PROVIDER_NETWORK_ERROR
    assert result.error.code == "SENTINEL_TEST_ADAPTER_ERROR"


def test_run_contract_invalid_provider_json_fails_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # REQ-F-004, REQ-F-007, REQ-F-014
    # invalid JSON → contract failure
    prompt_path, schema_path = _write_prompt_and_schema(tmp_path, {"type": "object"})

    class _FakeAdapter:
        def invoke(self, request: ProviderRequest) -> ProviderResponseNormalized:
            _ = request
            return ProviderResponseNormalized(raw_text="not-json")

    monkeypatch.setattr(
        "sentinel.core.runner.get_provider_adapter",
        lambda provider_name: _FakeAdapter(),
    )

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="openai",
        model="gpt-stub",
        timeout=5,
    )

    assert result.status == "FAIL"
    assert result.error is not None
    assert result.error.category == JSON_PARSE_ERROR


def test_run_contract_invalid_schema_structure_returns_error(tmp_path: Path) -> None:
    # REQ-D-002, REQ-F-015
    # invalid schema → execution error
    prompt_path, schema_path = _write_prompt_and_schema(
        tmp_path,
        {"type": "not-a-real-type"},
    )

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="openai",
        model="gpt-stub",
        timeout=5,
    )

    assert result.status == "ERROR"
    assert result.error is not None
    assert result.error.category == SCHEMA_INVALID


def test_run_contract_provider_network_failure_returns_execution_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # REQ-F-003, REQ-F-015
    # provider failure → execution error
    prompt_path, schema_path = _write_prompt_and_schema(tmp_path, {"type": "object"})

    adapter_error = SentinelError(
        category="PROVIDER_NETWORK_ERROR",
        code="SENTINEL_TEST_PROVIDER_NETWORK",
        message="network failed",
    )

    class _FakeAdapter:
        def invoke(self, request: ProviderRequest) -> SentinelError:
            _ = request
            return adapter_error

    monkeypatch.setattr(
        "sentinel.core.runner.get_provider_adapter",
        lambda provider_name: _FakeAdapter(),
    )

    result = run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider="openai",
        model="gpt-stub",
        timeout=5,
    )

    assert result.status == "ERROR"
    assert result.error is not None
    assert result.error.category == PROVIDER_NETWORK_ERROR
