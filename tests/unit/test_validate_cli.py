"""Unit tests for ``sentinel validate`` command behavior."""

from __future__ import annotations

import json

import pytest

from sentinel.cli import main


def test_validate_help_includes_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["validate", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "usage: sentinel validate" in captured.out
    assert "--input PATH" in captured.out
    assert "--schema PATH" in captured.out


def test_validate_pass_exit_0(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"},
                },
                "required": ["name", "age"],
            }
        ),
        encoding="utf-8",
    )
    input_path = tmp_path / "valid.json"
    input_path.write_text(json.dumps({"name": "John", "age": 30}), encoding="utf-8")

    exit_code = main(["validate", "--input", str(input_path), "--schema", str(schema_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "PASS: Contract satisfied" in captured.out


def test_validate_invalid_json_exit_1(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps({"type": "object", "properties": {"name": {"type": "string"}}}),
        encoding="utf-8",
    )
    input_path = tmp_path / "invalid.json"
    input_path.write_text("{invalid json", encoding="utf-8")

    exit_code = main(["validate", "--input", str(input_path), "--schema", str(schema_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAIL: Contract violated" in captured.out
    assert "JSON_PARSE_ERROR" in captured.out


def test_validate_schema_violation_exit_1(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                "required": ["name", "age"],
            }
        ),
        encoding="utf-8",
    )
    input_path = tmp_path / "violation.json"
    input_path.write_text(json.dumps({"name": "John"}), encoding="utf-8")

    exit_code = main(["validate", "--input", str(input_path), "--schema", str(schema_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "FAIL: Contract violated" in captured.out
    assert "SCHEMA_VALIDATION_ERROR" in captured.out


def test_validate_missing_input_file_exit_2(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        json.dumps({"type": "object", "properties": {"name": {"type": "string"}}}),
        encoding="utf-8",
    )
    missing_input = tmp_path / "missing.json"

    exit_code = main(["validate", "--input", str(missing_input), "--schema", str(schema_path)])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "ERROR: Execution failed" in captured.out
    assert "FILE_NOT_FOUND" in captured.out
