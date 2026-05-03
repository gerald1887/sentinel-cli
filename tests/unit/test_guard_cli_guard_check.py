"""CLI tests for Guard guard check command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel.cli import main


def _write_input(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_assertions(path: Path, yaml_text: str) -> None:
    path.write_text(yaml_text, encoding="utf-8")


def test_guard_check_pass_case_exact_output(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "out.json"
    assertions_path = tmp_path / "assertions.yaml"
    _write_input(input_path, {"a": 1})
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: ex1\n    type: exists\n    path: /a\n",
    )

    exit_code = main([
        "guard",
        "check",
        "--input",
        str(input_path),
        "--assertions",
        str(assertions_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "GUARD SUMMARY total=1 pass=1 fail=0 error=0\n"


def test_guard_check_fail_case_exact_assert_line(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "out.json"
    assertions_path = tmp_path / "assertions.yaml"
    _write_input(input_path, {"a": 1})
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: eq1\n    type: equals\n    path: /a\n    value: 2\n",
    )

    exit_code = main([
        "guard",
        "check",
        "--input",
        str(input_path),
        "--assertions",
        str(assertions_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == (
        "GUARD SUMMARY total=1 pass=0 fail=1 error=0\n"
        "ASSERT eq1 FAIL equals /a expected=2 actual=1\n"
    )


def test_guard_check_multiple_assertions_prints_only_fails_in_order(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "out.json"
    assertions_path = tmp_path / "assertions.yaml"
    _write_input(input_path, {"a": 1})
    _write_assertions(
        assertions_path,
        (
            "version: '1'\n"
            "assertions:\n"
            "  - id: p1\n"
            "    type: exists\n"
            "    path: /a\n"
            "  - id: f1\n"
            "    type: equals\n"
            "    path: /a\n"
            "    value: 2\n"
            "  - id: f2\n"
            "    type: not_exists\n"
            "    path: /a\n"
        ),
    )

    exit_code = main([
        "guard",
        "check",
        "--input",
        str(input_path),
        "--assertions",
        str(assertions_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == (
        "GUARD SUMMARY total=3 pass=1 fail=2 error=0\n"
        "ASSERT f1 FAIL equals /a expected=2 actual=1\n"
        "ASSERT f2 FAIL not_exists /a expected=None actual=1\n"
    )


def test_guard_check_evaluator_error_case(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "out.json"
    assertions_path = tmp_path / "assertions.yaml"
    _write_input(input_path, {"a": 1})
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: bad1\n    path: /a\n",
    )

    exit_code = main([
        "guard",
        "check",
        "--input",
        str(input_path),
        "--assertions",
        str(assertions_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == (
        "GUARD SUMMARY total=0 pass=0 fail=0 error=1\n"
        "INTERNAL_ERROR SENTINEL_ASSERTION_ERROR Guard evaluation failed.\n"
    )


def test_guard_check_file_error_case(tmp_path: Path, capsys) -> None:
    missing_input = tmp_path / "missing.json"
    assertions_path = tmp_path / "assertions.yaml"
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: ex1\n    type: exists\n    path: /a\n",
    )

    exit_code = main([
        "guard",
        "check",
        "--input",
        str(missing_input),
        "--assertions",
        str(assertions_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == (
        "GUARD SUMMARY total=0 pass=0 fail=0 error=1\n"
        "INTERNAL_ERROR SENTINEL_FILE_ERROR Failed to load input or assertions.\n"
    )


def test_guard_check_requires_flags() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["guard", "check", "--input", "out.json"])
    assert exc_info.value.code != 0


def test_guard_check_fail_output_uses_repr_for_strings(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "out.json"
    assertions_path = tmp_path / "assertions.yaml"
    _write_input(input_path, {"a": "actual-string"})
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: eqs\n    type: equals\n    path: /a\n    value: expected-string\n",
    )

    exit_code = main([
        "guard",
        "check",
        "--input",
        str(input_path),
        "--assertions",
        str(assertions_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == (
        "GUARD SUMMARY total=1 pass=0 fail=1 error=0\n"
        "ASSERT eqs FAIL equals /a expected='expected-string' actual='actual-string'\n"
    )

