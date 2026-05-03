"""Fixture-driven tests for unified artifact validation via the CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.cli import main


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_valid_unified_artifact_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo_root()
    schema = root / "examples/fixtures/contract_check/artifact_schema.json"
    fixture = root / "examples/fixtures/contract_check/artifact_valid.json"

    exit_code = main(["validate", "--input", str(fixture), "--schema", str(schema)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "PASS: Contract satisfied" in captured.out


def test_invalid_unified_artifact_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    root = _repo_root()
    schema = root / "examples/fixtures/contract_check/artifact_schema.json"
    fixture = root / "examples/fixtures/contract_check/artifact_invalid.json"

    exit_code = main(["validate", "--input", str(fixture), "--schema", str(schema)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAIL: Contract violated" in captured.out
    assert "SCHEMA_VALIDATION_ERROR" in captured.out
