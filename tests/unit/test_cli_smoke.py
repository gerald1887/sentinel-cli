"""Smoke tests for sentinel.cli – argument parsing and status mapping.

Requirements trace:
    # REQ-CLI-001 – Primary ``sentinel`` command exists and is callable.
    # REQ-CLI-002 – ``run`` subcommand accepts required flags.
    # REQ-CLI-004 – Deterministic status-to-exit mapping for run outcomes.

No provider calls are made; run_contract is monkeypatched.
"""

from __future__ import annotations

import sys
import types

import pytest

from sentinel.cli import main
from sentinel.core.errors import SentinelError
from sentinel.core.runner import RunResult
from sentinel.testkit.types import (
    RunCaseResult,
    RunSuiteResult,
    RunSummary,
    UpdateCaseResult,
    UpdateSuiteResult,
    UpdateSummary,
)


# REQ-CLI-001
class TestVersionFlag:
    """``sentinel --version`` must print version info and exit cleanly."""

    def test_version_exits_zero(self) -> None:
        # REQ-CLI-001 (primary command exists)
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0


# REQ-CLI-002
class TestRunSubcommandParsing:
    """``sentinel run`` maps runner status to expected CLI behavior."""

    def test_run_pass_maps_to_exit_0(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        # REQ-CLI-002 (accepts required flags)
        # REQ-CLI-004 (PASS maps to exit 0 and success output)
        monkeypatch.setattr(
            "sentinel.cli.run_contract",
            lambda **_: RunResult(status="PASS", error=None),
        )
        exit_code = main([
            "run",
            "--prompt", "x",
            "--schema", "y",
            "--provider", "openai",
            "--model", "gpt",
        ])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "PASS: Contract satisfied" in captured.out

    def test_run_fail_maps_to_exit_1(self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        # REQ-CLI-004 (FAIL maps to exit 1 and failure output)
        monkeypatch.setattr(
            "sentinel.cli.run_contract",
            lambda **_: RunResult(status="FAIL", error=None),
        )
        exit_code = main([
            "run",
            "--prompt", "x",
            "--schema", "y",
            "--provider", "openai",
            "--model", "gpt",
        ])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "FAIL: Contract violated" in captured.out

    def test_run_error_maps_to_exit_2(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # REQ-CLI-004 (ERROR maps to exit 2 and error output)
        monkeypatch.setattr(
            "sentinel.cli.run_contract",
            lambda **_: RunResult(status="ERROR", error=None),
        )
        exit_code = main([
            "run",
            "--prompt", "x",
            "--schema", "y",
            "--provider", "openai",
            "--model", "gpt",
        ])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "ERROR: Execution failed" in captured.out

    def test_run_fail_output_includes_structured_error_details(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # REQ-F-010, REQ-CLI-005
        # fail output includes structured error details
        monkeypatch.setattr(
            "sentinel.cli.run_contract",
            lambda **_: RunResult(
                status="FAIL",
                error=SentinelError(
                    category="JSON_PARSE_ERROR",
                    code="SENTINEL_JSON_PARSE_ERROR",
                    message="invalid json",
                ),
            ),
        )

        exit_code = main([
            "run",
            "--prompt", "x",
            "--schema", "y",
            "--provider", "openai",
            "--model", "gpt",
        ])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "FAIL: Contract violated" in captured.out
        assert "JSON_PARSE_ERROR" in captured.out
        assert "invalid json" in captured.out

    def test_run_error_output_includes_structured_diagnostics(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # REQ-F-015, REQ-CLI-005
        # error output includes structured diagnostics
        monkeypatch.setattr(
            "sentinel.cli.run_contract",
            lambda **_: RunResult(
                status="ERROR",
                error=SentinelError(
                    category="PROVIDER_TIMEOUT",
                    code="SENTINEL_PROVIDER_TIMEOUT",
                    message="timed out",
                ),
            ),
        )

        exit_code = main([
            "run",
            "--prompt", "x",
            "--schema", "y",
            "--provider", "openai",
            "--model", "gpt",
        ])
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "ERROR: Execution failed" in captured.out
        assert "PROVIDER_TIMEOUT" in captured.out
        assert "timed out" in captured.out

    def test_run_missing_required_flag_exits_nonzero(self) -> None:
        # REQ-CLI-002 (required flags are enforced by argparse)
        with pytest.raises(SystemExit) as exc_info:
            main(["run", "--prompt", "x"])
        assert exc_info.value.code != 0


class TestRegressionTestRunCli:
    """``sentinel test run`` CLI wiring is thin and deterministic."""

    def _install_fake_suite_runner(self, monkeypatch: pytest.MonkeyPatch, run_suite_impl) -> None:
        fake_module = types.SimpleNamespace(run_suite=run_suite_impl)
        monkeypatch.setitem(sys.modules, "sentinel.testkit.suite_runner", fake_module)

    def test_test_run_suite_level_error_exit_2(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        err = SentinelError(category="SCHEMA_INVALID", code="SENTINEL_SUITE_INVALID_YAML", message="bad yaml")
        self._install_fake_suite_runner(monkeypatch, lambda suite_path: err)

        exit_code = main(["test", "run", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "TEST RUN ERROR" in captured.out
        assert "SCHEMA_INVALID" in captured.out
        assert "SENTINEL_SUITE_INVALID_YAML" in captured.out
        assert "bad yaml" in captured.out

    def test_test_run_all_pass_prints_summary_only_exit_0(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        suite_result = RunSuiteResult(
            command="run",
            suite_path="suite.yaml",
            summary=RunSummary(total=2, pass_count=2, diff_count=0, error_count=0),
            cases=[
                RunCaseResult(case_id="c1", status="PASS"),
                RunCaseResult(case_id="c2", status="PASS"),
            ],
        )
        self._install_fake_suite_runner(monkeypatch, lambda suite_path: suite_result)

        exit_code = main(["test", "run", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "TEST SUMMARY" in captured.out
        assert "CASE " not in captured.out

    def test_test_run_diff_exit_1_prints_only_diff_case(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        suite_result = RunSuiteResult(
            command="run",
            suite_path="suite.yaml",
            summary=RunSummary(total=2, pass_count=1, diff_count=1, error_count=0),
            cases=[
                RunCaseResult(case_id="c1", status="PASS"),
                RunCaseResult(case_id="c2", status="DIFF"),
            ],
        )
        self._install_fake_suite_runner(monkeypatch, lambda suite_path: suite_result)

        exit_code = main(["test", "run", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "TEST SUMMARY" in captured.out
        assert "CASE c2 DIFF" in captured.out
        assert "CASE c1" not in captured.out

    def test_test_run_error_outranks_diff_exit_2_and_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        suite_result = RunSuiteResult(
            command="run",
            suite_path="suite.yaml",
            summary=RunSummary(total=3, pass_count=1, diff_count=1, error_count=1),
            cases=[
                RunCaseResult(case_id="c1", status="PASS"),
                RunCaseResult(case_id="c2", status="ERROR", errors=["PROVIDER_TIMEOUT|X|timed out"]),
                RunCaseResult(case_id="c3", status="DIFF"),
            ],
        )
        self._install_fake_suite_runner(monkeypatch, lambda suite_path: suite_result)

        exit_code = main(["test", "run", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "TEST SUMMARY" in captured.out
        # Only non-PASS cases, in order.
        assert captured.out.index("CASE c2 ERROR") < captured.out.index("CASE c3 DIFF")

    def test_test_run_requires_suite_flag(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["test", "run"])
        assert exc_info.value.code != 0


class TestRegressionTestUpdateCli:
    """``sentinel test update`` CLI wiring is thin and deterministic."""

    def _install_fake_update_runner(self, monkeypatch: pytest.MonkeyPatch, run_update_impl) -> None:
        fake_module = types.SimpleNamespace(run_update=run_update_impl)
        monkeypatch.setitem(sys.modules, "sentinel.testkit.update_runner", fake_module)

    def test_test_update_suite_level_error_exit_2(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        err = SentinelError(category="SCHEMA_INVALID", code="SENTINEL_SUITE_INVALID_YAML", message="bad yaml")
        self._install_fake_update_runner(monkeypatch, lambda suite_path: err)

        exit_code = main(["test", "update", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "TEST UPDATE ERROR" in captured.out
        assert "SCHEMA_INVALID" in captured.out
        assert "SENTINEL_SUITE_INVALID_YAML" in captured.out
        assert "bad yaml" in captured.out

    def test_test_update_all_updated_summary_only_exit_0(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        update_result = UpdateSuiteResult(
            command="update",
            suite_path="suite.yaml",
            summary=UpdateSummary(total=2, updated=2, errors=0),
            cases=[
                UpdateCaseResult(case_id="c1", status="UPDATED"),
                UpdateCaseResult(case_id="c2", status="UPDATED"),
            ],
        )
        self._install_fake_update_runner(monkeypatch, lambda suite_path: update_result)

        exit_code = main(["test", "update", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "TEST UPDATE SUMMARY" in captured.out
        assert "CASE " not in captured.out

    def test_test_update_case_error_exit_2_only_error_lines_in_order(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        update_result = UpdateSuiteResult(
            command="update",
            suite_path="suite.yaml",
            summary=UpdateSummary(total=3, updated=1, errors=2),
            cases=[
                UpdateCaseResult(case_id="c1", status="UPDATED"),
                UpdateCaseResult(case_id="c2", status="ERROR", errors=["E2"]),
                UpdateCaseResult(case_id="c3", status="ERROR", errors=["E3"]),
            ],
        )
        self._install_fake_update_runner(monkeypatch, lambda suite_path: update_result)

        exit_code = main(["test", "update", "--suite", "suite.yaml"])
        captured = capsys.readouterr()

        assert exit_code == 2
        assert "TEST UPDATE SUMMARY" in captured.out
        assert "CASE c1" not in captured.out
        assert captured.out.index("CASE c2 ERROR E2") < captured.out.index("CASE c3 ERROR E3")

    def test_test_update_requires_suite_flag(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["test", "update"])
        assert exc_info.value.code != 0


class TestGuardCheckCli:
    """``sentinel guard check`` CLI wiring is deterministic for external integration."""

    def test_guard_check_requires_flags(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["guard", "check", "--input", "out.json"])
        assert exc_info.value.code != 0
