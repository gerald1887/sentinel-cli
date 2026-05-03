"""Unit tests for Regression update-suite orchestrator."""

from __future__ import annotations

import sys
import types

sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda _: {}))

from sentinel.core.errors import SentinelError
from sentinel.testkit.types import SuiteCaseDefinition, SuiteDefinition
from sentinel.testkit.update_runner import run_update


def _suite_with_cases(case_ids: list[str]) -> SuiteDefinition:
    return SuiteDefinition(
        command="update",
        suite_path="/tmp/suite.yaml",
        cases=[
            SuiteCaseDefinition(
                case_id=case_id,
                prompt=f"{case_id}.prompt.txt",
                schema=f"{case_id}.schema.json",
                provider="openai",
                model="gpt-4.1",
                timeout=60,
            )
            for case_id in case_ids
        ],
    )


def test_run_update_loader_error_passthrough(monkeypatch) -> None:
    err = SentinelError(
        category="SCHEMA_INVALID",
        code="SENTINEL_SUITE_INVALID_YAML",
        message="bad yaml",
    )
    monkeypatch.setattr("sentinel.testkit.update_runner.load_suite", lambda _: err)

    result = run_update("/tmp/suite.yaml")
    assert isinstance(result, SentinelError)
    assert result is err


def test_run_update_single_updated_case(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.update_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.update_runner.execute_case", lambda case: {"k": 1})
    monkeypatch.setattr(
        "sentinel.testkit.update_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )
    monkeypatch.setattr("sentinel.testkit.update_runner.write_snapshot", lambda p, o: None)

    result = run_update("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.summary.total == 1
    assert result.summary.updated == 1
    assert result.summary.errors == 0
    assert result.cases[0].status == "UPDATED"


def test_run_update_execution_error_maps_to_case_error(monkeypatch) -> None:
    exec_err = SentinelError(category="PROVIDER_TIMEOUT", code="X", message="timed out")
    monkeypatch.setattr(
        "sentinel.testkit.update_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.update_runner.execute_case", lambda case: exec_err)

    result = run_update("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.cases[0].status == "ERROR"
    assert "PROVIDER_TIMEOUT|X|timed out" in result.cases[0].errors


def test_run_update_write_error_maps_to_case_error(monkeypatch) -> None:
    write_err = SentinelError(category="FILE_READ_ERROR", code="Y", message="nope")
    monkeypatch.setattr(
        "sentinel.testkit.update_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.update_runner.execute_case", lambda case: {"k": 1})
    monkeypatch.setattr(
        "sentinel.testkit.update_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )
    monkeypatch.setattr("sentinel.testkit.update_runner.write_snapshot", lambda p, o: write_err)

    result = run_update("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.cases[0].status == "ERROR"
    assert "FILE_READ_ERROR|Y|nope" in result.cases[0].errors


def test_run_update_mixed_cases_order_and_counts(monkeypatch) -> None:
    suite = _suite_with_cases(["c1", "c2", "c3"])
    monkeypatch.setattr("sentinel.testkit.update_runner.load_suite", lambda _: suite)

    def _exec(case):
        if case.case_id == "c1":
            return {"v": 1}
        if case.case_id == "c2":
            return {"v": 2}
        return SentinelError(category="PROVIDER_NETWORK_ERROR", code="X", message="net")

    monkeypatch.setattr("sentinel.testkit.update_runner.execute_case", _exec)
    monkeypatch.setattr(
        "sentinel.testkit.update_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )

    def _write(path: str, output: object):
        if path.endswith("/c2.json"):
            return SentinelError(category="FILE_READ_ERROR", code="Y", message="disk")
        return None

    monkeypatch.setattr("sentinel.testkit.update_runner.write_snapshot", _write)

    result = run_update("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert [c.case_id for c in result.cases] == ["c1", "c2", "c3"]
    assert [c.status for c in result.cases] == ["UPDATED", "ERROR", "ERROR"]
    assert result.summary.total == 3
    assert result.summary.updated == 1
    assert result.summary.errors == 2


def test_run_update_dependency_call_order_and_arguments(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    suite = _suite_with_cases(["a"])
    monkeypatch.setattr("sentinel.testkit.update_runner.load_suite", lambda _: suite)

    def _exec(case):
        calls.append(("execute_case", case.case_id))
        return {"k": 1}

    def _resolve(suite_path, case_id):
        calls.append(("resolve_snapshot_path", f"{suite_path}:{case_id}"))
        return f"/tmp/snapshots/{case_id}.json"

    def _write(path: str, output: object):
        calls.append(("write_snapshot", f"{path}:{output}"))
        return None

    monkeypatch.setattr("sentinel.testkit.update_runner.execute_case", _exec)
    monkeypatch.setattr("sentinel.testkit.update_runner.resolve_snapshot_path", _resolve)
    monkeypatch.setattr("sentinel.testkit.update_runner.write_snapshot", _write)

    run_update("/tmp/suite.yaml")

    assert calls == [
        ("execute_case", "a"),
        ("resolve_snapshot_path", "/tmp/suite.yaml:a"),
        ("write_snapshot", "/tmp/snapshots/a.json:{'k': 1}"),
    ]


def test_run_update_unexpected_exception_in_path_resolution_becomes_case_error_and_continues(
    monkeypatch,
) -> None:
    suite = _suite_with_cases(["a", "b"])
    monkeypatch.setattr("sentinel.testkit.update_runner.load_suite", lambda _: suite)
    monkeypatch.setattr("sentinel.testkit.update_runner.execute_case", lambda case: {"k": 1})

    def _resolve(suite_path, case_id):
        if case_id == "a":
            raise RuntimeError("boom")
        return f"/tmp/snapshots/{case_id}.json"

    monkeypatch.setattr("sentinel.testkit.update_runner.resolve_snapshot_path", _resolve)
    monkeypatch.setattr("sentinel.testkit.update_runner.write_snapshot", lambda p, o: None)

    result = run_update("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert [c.case_id for c in result.cases] == ["a", "b"]
    assert [c.status for c in result.cases] == ["ERROR", "UPDATED"]
    assert result.summary.updated == 1
    assert result.summary.errors == 1
    assert "SENTINEL_UPDATE_SNAPSHOT_PATH_ERROR" in result.cases[0].errors[0]

