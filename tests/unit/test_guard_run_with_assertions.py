"""Tests for optional ``sentinel run --assertions`` integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.cli import main
from sentinel.core.runner import RunResult


def _write_assertions(path: Path, yaml_text: str) -> None:
    path.write_text(yaml_text, encoding="utf-8")


def _run_args(assertions_path: str | None = None) -> list[str]:
    args = [
        "run",
        "--prompt", "prompt.txt",
        "--schema", "schema.json",
        "--provider", "openai",
        "--model", "gpt",
    ]
    if assertions_path is not None:
        args.extend(["--assertions", assertions_path])
    return args


def test_run_success_without_assertions_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sentinel.cli.run_contract",
        lambda **_: RunResult(status="PASS", error=None, approved_output={"x": 1}),
    )

    exit_code = main(_run_args())
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "PASS: Contract satisfied\n"


def test_run_success_with_assertions_guard_pass_preserves_success_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sentinel.cli.run_contract",
        lambda **_: RunResult(status="PASS", error=None, approved_output={"a": 1}),
    )
    assertions_path = tmp_path / "assertions.yaml"
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: ex1\n    type: exists\n    path: /a\n",
    )

    exit_code = main(_run_args(str(assertions_path)))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "PASS: Contract satisfied\n"


def test_run_success_with_assertions_guard_fail_returns_guard_fail_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sentinel.cli.run_contract",
        lambda **_: RunResult(status="PASS", error=None, approved_output={"a": 1}),
    )
    assertions_path = tmp_path / "assertions.yaml"
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: eq1\n    type: equals\n    path: /a\n    value: 2\n",
    )

    exit_code = main(_run_args(str(assertions_path)))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == (
        "GUARD SUMMARY total=1 pass=0 fail=1 error=0\n"
        "ASSERT eq1 FAIL equals /a expected=2 actual=1\n"
    )


def test_run_success_with_malformed_assertions_returns_guard_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sentinel.cli.run_contract",
        lambda **_: RunResult(status="PASS", error=None, approved_output={"a": 1}),
    )
    assertions_path = tmp_path / "assertions.yaml"
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: bad1\n    path: /a\n",
    )

    exit_code = main(_run_args(str(assertions_path)))
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == (
        "GUARD SUMMARY total=0 pass=0 fail=0 error=1\n"
        "INTERNAL_ERROR SENTINEL_ASSERTION_ERROR Guard evaluation failed.\n"
    )


def test_base_run_fail_does_not_invoke_guard_evaluation_and_preserves_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sentinel.cli.run_contract",
        lambda **_: RunResult(status="FAIL", error=None, approved_output={"a": 1}),
    )

    guard_called = {"value": False}

    def _fake_eval(_input_json, _assertions):
        guard_called["value"] = True
        raise AssertionError("evaluate_assertions should not be called for base FAIL")

    monkeypatch.setattr("sentinel.cli.evaluate_assertions", _fake_eval)
    assertions_path = tmp_path / "assertions.yaml"
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: ex1\n    type: exists\n    path: /a\n",
    )

    exit_code = main(_run_args(str(assertions_path)))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert guard_called["value"] is False
    assert captured.out == "FAIL: Contract violated\n"


def test_base_run_error_does_not_invoke_guard_evaluation_and_preserves_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sentinel.cli.run_contract",
        lambda **_: RunResult(status="ERROR", error=None, approved_output={"a": 1}),
    )

    guard_called = {"value": False}

    def _fake_eval(_input_json, _assertions):
        guard_called["value"] = True
        raise AssertionError("evaluate_assertions should not be called for base ERROR")

    monkeypatch.setattr("sentinel.cli.evaluate_assertions", _fake_eval)
    assertions_path = tmp_path / "assertions.yaml"
    _write_assertions(
        assertions_path,
        "version: '1'\nassertions:\n  - id: ex1\n    type: exists\n    path: /a\n",
    )

    exit_code = main(_run_args(str(assertions_path)))
    captured = capsys.readouterr()

    assert exit_code == 2
    assert guard_called["value"] is False
    assert captured.out == "ERROR: Execution failed\n"

