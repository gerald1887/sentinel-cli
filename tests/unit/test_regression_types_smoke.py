"""Smoke tests for Regression internal testkit types."""

from __future__ import annotations

from sentinel.testkit.types import (
    DiffEntry,
    RunCaseResult,
    RunSuiteResult,
    RunSummary,
    SuiteCaseDefinition,
    SuiteDefinition,
    UpdateCaseResult,
    UpdateSuiteResult,
    UpdateSummary,
)


def test_regression_types_instantiation_and_defaults() -> None:
    diff = DiffEntry(record_type="mismatch", path="/foo/bar", expected=1, actual=2)
    assert diff.record_type == "mismatch"
    assert diff.path == "/foo/bar"

    run_case_a = RunCaseResult(case_id="case-a", status="PASS")
    run_case_b = RunCaseResult(case_id="case-b", status="DIFF")
    run_case_b.diffs.append(diff)
    run_case_b.errors.append("diff found")
    assert run_case_a.diffs == []
    assert run_case_a.errors == []
    assert run_case_b.diffs == [diff]
    assert run_case_b.errors == ["diff found"]

    run_summary = RunSummary(total=2, pass_count=1, diff_count=1, error_count=0)
    run_suite = RunSuiteResult(
        command="run",
        suite_path="suite.yaml",
        summary=run_summary,
        cases=[run_case_a, run_case_b],
    )
    assert run_suite.command == "run"
    assert run_suite.suite_path == "suite.yaml"
    assert run_suite.summary == run_summary
    assert run_suite.cases[1].status == "DIFF"

    update_case_a = UpdateCaseResult(case_id="case-c", status="UPDATED")
    update_case_b = UpdateCaseResult(case_id="case-d", status="ERROR")
    update_case_b.errors.append("update failed")
    assert update_case_a.errors == []
    assert update_case_b.errors == ["update failed"]

    update_summary = UpdateSummary(total=2, updated=1, errors=1)
    update_suite = UpdateSuiteResult(
        command="update",
        suite_path="suite.yaml",
        summary=update_summary,
        cases=[update_case_a, update_case_b],
    )
    assert update_suite.command == "update"
    assert update_suite.summary.updated == 1
    assert update_suite.cases[0].status == "UPDATED"


def test_regression_locked_literal_values_in_examples() -> None:
    assert DiffEntry(record_type="missing", path="/a").record_type == "missing"
    assert DiffEntry(record_type="extra", path="/b").record_type == "extra"
    assert DiffEntry(record_type="mismatch", path="/c").record_type == "mismatch"

    assert RunCaseResult(case_id="x", status="PASS").status == "PASS"
    assert RunCaseResult(case_id="x", status="DIFF").status == "DIFF"
    assert RunCaseResult(case_id="x", status="ERROR").status == "ERROR"

    assert UpdateCaseResult(case_id="x", status="UPDATED").status == "UPDATED"
    assert UpdateCaseResult(case_id="x", status="ERROR").status == "ERROR"


def test_regression_suite_definition_types_smoke() -> None:
    case = SuiteCaseDefinition(
        case_id="case-1",
        prompt="prompt.txt",
        schema="schema.json",
        provider="openai",
        model="gpt-4.1",
        timeout=60,
    )
    suite = SuiteDefinition(command="run", suite_path="suite.yaml", cases=[case])
    assert suite.command == "run"
    assert suite.cases[0].case_id == "case-1"

