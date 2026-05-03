"""Monitor integration tests for monitor check CLI."""

from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main
from sentinel.monitor.event_store import append_event
from sentinel.monitor.types import EVENT_VERSION, Event


def _event(event_id: str, status: str, provider: str | None) -> Event:
    return Event(
        event_version=EVENT_VERSION,
        event_id=event_id,
        event_type="contract.run",
        timestamp_utc=f"2026-01-0{event_id}T00:00:00Z",
        command="run",
        provider=provider,
        model="m1",
        suite_case_id=f"c{event_id}",
        status=status,
        exit_code=0,
        duration_ms=10,
        contract_status=None,
        guard_status=None,
        drift_status=None,
        error_category=None,
        error_code=None,
        refusal_detected=None,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        artifact_refs={"source": "s"},
        metadata=None,
    )


def _seed_events(path: str) -> None:
    assert append_event(path, _event("1", "PASS", "openai")) is None
    assert append_event(path, _event("2", "FAIL", "anthropic")) is None
    assert append_event(path, _event("3", "PASS", "openai")) is None


def _write_json(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return str(path)


def _run_check(event_file: str, signals: str, rules: str, extra: list[str] | None = None) -> int:
    argv = [
        "monitor",
        "check",
        "--event-file",
        event_file,
        "--signals",
        signals,
        "--rules",
        rules,
    ]
    if extra:
        argv.extend(extra)
    return main(argv)


def test_check_end_to_end_and_deterministic_output(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)
    signals = _write_json(
        tmp_path / "signals.json",
        {"signals": [{"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}]},
    )
    rules = _write_json(
        tmp_path / "rules.json",
        {"rules": [{"id": "r1", "signal": "pass_count", "operator": "eq", "expected": 2, "message": "ok"}]},
    )

    assert _run_check(event_file, signals, rules) == 0
    first = capsys.readouterr().out
    assert _run_check(event_file, signals, rules) == 0
    second = capsys.readouterr().out
    assert first == second
    assert "MONITOR CHECK SUMMARY total_rules=1 pass=1 fail=0 error=0 events=3" in first


def test_only_fail_and_error_rule_lines_printed(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)
    signals = _write_json(
        tmp_path / "signals.json",
        {"signals": [{"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}]},
    )
    rules = _write_json(
        tmp_path / "rules.json",
        {
            "rules": [
                {"id": "pass", "signal": "pass_count", "operator": "eq", "expected": 2, "message": "ok"},
                {"id": "fail", "signal": "pass_count", "operator": "eq", "expected": 1, "message": "bad"},
                {"id": "err", "signal": "pass_count", "operator": "eq", "expected": "2", "message": "bad"},
            ]
        },
    )
    exit_code = _run_check(event_file, signals, rules)
    out = capsys.readouterr().out
    assert exit_code == 2
    assert "RULE FAIL fail" in out
    assert "RULE ERROR err" in out
    assert "RULE FAIL pass" not in out


def test_pass_only_exit_0_fail_exit_1_error_exit_2(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)
    signals = _write_json(
        tmp_path / "signals.json",
        {"signals": [{"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}]},
    )
    pass_rules = _write_json(
        tmp_path / "pass_rules.json",
        {"rules": [{"id": "r1", "signal": "pass_count", "operator": "eq", "expected": 2, "message": "ok"}]},
    )
    fail_rules = _write_json(
        tmp_path / "fail_rules.json",
        {"rules": [{"id": "r2", "signal": "pass_count", "operator": "eq", "expected": 1, "message": "bad"}]},
    )
    err_rules = _write_json(
        tmp_path / "err_rules.json",
        {"rules": [{"id": "r3", "signal": "pass_count", "operator": "eq", "expected": "2", "message": "bad"}]},
    )
    assert _run_check(event_file, signals, pass_rules) == 0
    _ = capsys.readouterr()
    assert _run_check(event_file, signals, fail_rules) == 1
    _ = capsys.readouterr()
    assert _run_check(event_file, signals, err_rules) == 2


def test_missing_invalid_input_files_exit_2(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)
    signals = _write_json(
        tmp_path / "signals.json",
        {"signals": [{"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}]},
    )
    rules = _write_json(
        tmp_path / "rules.json",
        {"rules": [{"id": "r1", "signal": "pass_count", "operator": "eq", "expected": 2, "message": "ok"}]},
    )

    assert _run_check(str(tmp_path / "missing.jsonl"), signals, rules) == 2
    _ = capsys.readouterr()
    assert _run_check(event_file, str(tmp_path / "missing_signals.json"), rules) == 2
    _ = capsys.readouterr()
    assert _run_check(event_file, signals, str(tmp_path / "missing_rules.json")) == 2
