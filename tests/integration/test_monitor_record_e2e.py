"""Monitor integration tests for monitor record CLI."""

from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main
from sentinel.monitor.event_store import read_events


def _write_source(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return str(path)


def _run_record(event_file: str, source: str, event_type: str) -> int:
    return main(
        [
            "monitor",
            "record",
            "--event-file",
            event_file,
            "--source",
            source,
            "--event-type",
            event_type,
        ]
    )


def test_valid_monitor_record_appends_exactly_one_event(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    source = _write_source(
        tmp_path / "source.json",
        {"command": "run", "status": "PASS", "exit_code": 0, "duration_ms": 100, "suite_case_id": "c1"},
    )

    exit_code = _run_record(event_file=event_file, source=source, event_type="contract.run")
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == ""

    events = read_events(event_file)
    assert isinstance(events, list)
    assert len(events) == 1
    assert events[0].event_type == "contract.run"
    assert events[0].suite_case_id == "c1"
    assert events[0].event_version == "1.0"


def test_repeated_monitor_record_appends_in_order(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    s1 = _write_source(
        tmp_path / "s1.json",
        {"command": "run", "status": "PASS", "exit_code": 0, "duration_ms": 10, "suite_case_id": "a"},
    )
    s2 = _write_source(
        tmp_path / "s2.json",
        {"command": "run", "status": "FAIL", "exit_code": 1, "duration_ms": 11, "suite_case_id": "b"},
    )

    assert _run_record(event_file=event_file, source=s1, event_type="contract.run") == 0
    _ = capsys.readouterr()
    assert _run_record(event_file=event_file, source=s2, event_type="contract.run") == 0
    _ = capsys.readouterr()

    events = read_events(event_file)
    assert isinstance(events, list)
    assert [event.suite_case_id for event in events] == ["a", "b"]


def test_invalid_source_artifact_returns_exit_2(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    bad_source = tmp_path / "bad.json"
    bad_source.write_text('{"case_id":"missing-status"}', encoding="utf-8")

    exit_code = _run_record(event_file=event_file, source=str(bad_source), event_type="contract.run")
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "MONITOR RECORD ERROR" in captured.out
    assert "SENTINEL_EVENT_SOURCE_INVALID" in captured.out


def test_cli_output_is_deterministic(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    source = _write_source(
        tmp_path / "source.json",
        {"command": "run", "status": "PASS", "exit_code": 0, "duration_ms": 100, "suite_case_id": "fixed"},
    )

    assert _run_record(event_file=event_file, source=source, event_type="contract.run") == 0
    first = capsys.readouterr().out
    assert _run_record(event_file=event_file, source=source, event_type="contract.run") == 0
    second = capsys.readouterr().out

    assert first == second == ""
