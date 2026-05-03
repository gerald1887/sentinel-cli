"""Unit tests for Regression run-suite orchestrator."""

from __future__ import annotations

import sys
import types

sys.modules.setdefault("yaml", types.SimpleNamespace(safe_load=lambda _: {}))

from sentinel.core.errors import SentinelError
from sentinel.testkit.suite_runner import run_suite
from sentinel.testkit.types import DiffEntry, SuiteCaseDefinition, SuiteDefinition


def _suite_with_cases(
    case_ids: list[str],
    *,
    ignore_paths_by_id: dict[str, tuple[str, ...]] | None = None,
) -> SuiteDefinition:
    ignore_paths_by_id = ignore_paths_by_id or {}
    return SuiteDefinition(
        command="run",
        suite_path="/tmp/suite.yaml",
        cases=[
            SuiteCaseDefinition(
                case_id=case_id,
                prompt=f"{case_id}.prompt.txt",
                schema=f"{case_id}.schema.json",
                provider="openai",
                model="gpt-4.1",
                timeout=60,
                ignore_paths=ignore_paths_by_id.get(case_id, ()),
            )
            for case_id in case_ids
        ],
    )


def test_run_suite_loader_top_level_failure_passthrough(monkeypatch) -> None:
    err = SentinelError(
        category="SCHEMA_INVALID",
        code="SENTINEL_SUITE_INVALID_YAML",
        message="bad yaml",
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.load_suite", lambda _: err)

    result = run_suite("/tmp/suite.yaml")
    assert isinstance(result, SentinelError)
    assert result is err


def test_run_suite_single_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", lambda case: {"k": 1})
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.read_snapshot", lambda _: {"k": 1})
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.compare_json",
        lambda e, a, ignore_paths=(): [],
    )

    result = run_suite("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.summary.total == 1
    assert result.summary.pass_count == 1
    assert result.summary.diff_count == 0
    assert result.summary.error_count == 0
    assert result.cases[0].status == "PASS"


def test_run_suite_single_diff(monkeypatch) -> None:
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", lambda case: {"k": 2})
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.read_snapshot", lambda _: {"k": 1})
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.compare_json",
        lambda e, a, ignore_paths=(): [
            DiffEntry(record_type="mismatch", path="/k", expected=1, actual=2)
        ],
    )

    result = run_suite("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.summary.total == 1
    assert result.summary.pass_count == 0
    assert result.summary.diff_count == 1
    assert result.summary.error_count == 0
    assert result.cases[0].status == "DIFF"
    assert result.cases[0].diffs[0].path == "/k"


def test_run_suite_execution_error_maps_to_case_error(monkeypatch) -> None:
    exec_err = SentinelError(
        category="PROVIDER_TIMEOUT",
        code="SENTINEL_PROVIDER_TIMEOUT",
        message="timed out",
    )
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", lambda case: exec_err)

    result = run_suite("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.summary.error_count == 1
    assert result.cases[0].status == "ERROR"
    assert "PROVIDER_TIMEOUT|SENTINEL_PROVIDER_TIMEOUT|timed out" in result.cases[0].errors


def test_run_suite_snapshot_read_error_maps_to_case_error(monkeypatch) -> None:
    read_err = SentinelError(
        category="FILE_NOT_FOUND",
        code="SENTINEL_FILE_NOT_FOUND",
        message="missing file",
    )
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.load_suite", lambda _: _suite_with_cases(["a"])
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", lambda case: {"ok": True})
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.read_snapshot", lambda _: read_err)

    result = run_suite("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert result.summary.error_count == 1
    assert result.cases[0].status == "ERROR"
    assert "FILE_NOT_FOUND|SENTINEL_FILE_NOT_FOUND|missing file" in result.cases[0].errors


def test_run_suite_mixed_results_order_and_counts(monkeypatch) -> None:
    suite = _suite_with_cases(["c1", "c2", "c3"])
    monkeypatch.setattr("sentinel.testkit.suite_runner.load_suite", lambda _: suite)

    def _exec(case):
        if case.case_id == "c1":
            return {"v": 1}
        if case.case_id == "c2":
            return {"v": 2}
        return SentinelError(category="PROVIDER_NETWORK_ERROR", code="X", message="net")

    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", _exec)
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )

    def _read(path: str):
        if path.endswith("/c1.json"):
            return {"v": 1}
        if path.endswith("/c2.json"):
            return {"v": 1}
        return {"unused": True}

    monkeypatch.setattr("sentinel.testkit.suite_runner.read_snapshot", _read)
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.compare_json",
        lambda e, a, ignore_paths=(): []
        if e == a
        else [DiffEntry(record_type="mismatch", path="/v", expected=1, actual=2)],
    )

    result = run_suite("/tmp/suite.yaml")
    assert not isinstance(result, SentinelError)
    assert [c.case_id for c in result.cases] == ["c1", "c2", "c3"]
    assert [c.status for c in result.cases] == ["PASS", "DIFF", "ERROR"]
    assert result.summary.total == 3
    assert result.summary.pass_count == 1
    assert result.summary.diff_count == 1
    assert result.summary.error_count == 1


def test_run_suite_dependency_call_order_and_arguments(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    suite = _suite_with_cases(["a"])
    monkeypatch.setattr("sentinel.testkit.suite_runner.load_suite", lambda _: suite)

    def _exec(case):
        calls.append(("execute_case", case.case_id))
        return {"k": 1}

    def _resolve(suite_path, case_id):
        calls.append(("resolve_snapshot_path", f"{suite_path}:{case_id}"))
        return f"/tmp/snapshots/{case_id}.json"

    def _read(path):
        calls.append(("read_snapshot", path))
        return {"k": 1}

    def _compare(expected, actual, ignore_paths=()):
        calls.append(("compare_json", f"{expected}->{actual}", ignore_paths))
        return []

    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", _exec)
    monkeypatch.setattr("sentinel.testkit.suite_runner.resolve_snapshot_path", _resolve)
    monkeypatch.setattr("sentinel.testkit.suite_runner.read_snapshot", _read)
    monkeypatch.setattr("sentinel.testkit.suite_runner.compare_json", _compare)

    run_suite("/tmp/suite.yaml")

    assert calls == [
        ("execute_case", "a"),
        ("resolve_snapshot_path", "/tmp/suite.yaml:a"),
        ("read_snapshot", "/tmp/snapshots/a.json"),
        ("compare_json", "{'k': 1}->{'k': 1}", ()),
    ]


def test_run_suite_passes_ignore_paths_to_compare_json(monkeypatch) -> None:
    suite = _suite_with_cases(["a"], ignore_paths_by_id={"a": ("/x", "/y")})
    monkeypatch.setattr("sentinel.testkit.suite_runner.load_suite", lambda _: suite)
    monkeypatch.setattr("sentinel.testkit.suite_runner.execute_case", lambda case: {"k": 1})
    monkeypatch.setattr(
        "sentinel.testkit.suite_runner.resolve_snapshot_path",
        lambda suite_path, case_id: f"/tmp/snapshots/{case_id}.json",
    )
    monkeypatch.setattr("sentinel.testkit.suite_runner.read_snapshot", lambda _: {"k": 1})

    received: list[tuple[object, object, tuple[str, ...]]] = []

    def _compare(expected, actual, ignore_paths=()):
        received.append((expected, actual, ignore_paths))
        return []

    monkeypatch.setattr("sentinel.testkit.suite_runner.compare_json", _compare)

    run_suite("/tmp/suite.yaml")
    assert len(received) == 1
    assert received[0][2] == ("/x", "/y")

