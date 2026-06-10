"""Minimal CLI e2e tests with deterministic provider stubs."""

from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main
from sentinel.providers.base import ProviderResponseNormalized


def _write_prompt_and_schema(tmp_path: Path, schema_obj: dict) -> tuple[str, str]:
    prompt_path = tmp_path / "prompt.txt"
    schema_path = tmp_path / "schema.json"
    prompt_path.write_text("Return JSON.", encoding="utf-8")
    schema_path.write_text(json.dumps(schema_obj), encoding="utf-8")
    return str(prompt_path), str(schema_path)


def _run_cli(prompt: str, schema: str) -> int:
    return main(
        [
            "run",
            "--prompt",
            prompt,
            "--schema",
            schema,
            "--provider",
            "openai",
            "--model",
            "gpt-4.1",
        ]
    )


def test_cli_e2e_pass_case(tmp_path: Path, monkeypatch, capsys) -> None:
    prompt, schema = _write_prompt_and_schema(tmp_path, {"type": "object"})

    class _Adapter:
        def invoke(self, request):
            _ = request
            return ProviderResponseNormalized(raw_text="{}")

    monkeypatch.setattr("sentinel.core.runner.get_provider_adapter", lambda _: _Adapter())

    exit_code = _run_cli(prompt, schema)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "PASS: Contract satisfied" in captured.out


def test_cli_e2e_fail_schema_violation(tmp_path: Path, monkeypatch, capsys) -> None:
    prompt, schema = _write_prompt_and_schema(
        tmp_path,
        {"type": "object", "required": ["x"], "properties": {"x": {"type": "string"}}},
    )

    class _Adapter:
        def invoke(self, request):
            _ = request
            return ProviderResponseNormalized(raw_text="{}")

    monkeypatch.setattr("sentinel.core.runner.get_provider_adapter", lambda _: _Adapter())

    exit_code = _run_cli(prompt, schema)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAIL: Contract violated" in captured.out


def test_cli_e2e_fail_invalid_json(tmp_path: Path, monkeypatch, capsys) -> None:
    prompt, schema = _write_prompt_and_schema(tmp_path, {"type": "object"})

    class _Adapter:
        def invoke(self, request):
            _ = request
            return ProviderResponseNormalized(raw_text="not-json")

    monkeypatch.setattr("sentinel.core.runner.get_provider_adapter", lambda _: _Adapter())

    exit_code = _run_cli(prompt, schema)
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAIL: Contract violated" in captured.out


def test_cli_e2e_error_missing_file(tmp_path: Path, capsys) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    missing_prompt = str(tmp_path / "missing_prompt.txt")

    exit_code = _run_cli(missing_prompt, str(schema_path))
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "ERROR: Execution failed" in captured.out
