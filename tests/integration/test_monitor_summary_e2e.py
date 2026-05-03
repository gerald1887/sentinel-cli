"""Monitor integration tests for monitor summary CLI."""

from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main
from sentinel.monitor.event_store import append_event
from sentinel.monitor.types import EVENT_VERSION, Event


def _event(event_id: str, status: str, provider: str | None, total_tokens: int | None) -> Event:
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
        total_tokens=total_tokens,
        artifact_refs={"source": "s"},
        metadata=None,
    )


def _seed_events(event_file: str) -> None:
    assert append_event(event_file, _event("1", "PASS", "openai", 100)) is None
    assert append_event(event_file, _event("2", "FAIL", "anthropic", None)) is None
    assert append_event(event_file, _event("3", "PASS", "openai", 300)) is None


def _write_signals(path: Path) -> str:
    payload = {
        "signals": [
            {"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}},
            {"name": "pass_rate", "type": "rate", "options": {"field": "status", "equals": "PASS"}},
        ]
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return str(path)


def _run_summary(event_file: str, signals_file: str, extra: list[str] | None = None) -> int:
    argv = ["monitor", "summary", "--event-file", event_file, "--signals", signals_file]
    if extra:
        argv.extend(extra)
    return main(argv)


def test_summary_computes_signals_from_event_file(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    signals_file = _write_signals(tmp_path / "signals.json")
    _seed_events(event_file)

    exit_code = _run_summary(event_file, signals_file)
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "MONITOR SUMMARY" in captured
    assert "signals=2 selected_events=3" in captured
    assert "SIGNAL pass_count value=2 events=3" in captured
    assert 'SIGNAL pass_rate value={"denominator":3,"numerator":2} events=3' in captured


def test_summary_respects_filters_reuse_selector(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    signals_file = _write_signals(tmp_path / "signals.json")
    _seed_events(event_file)

    exit_code = _run_summary(event_file, signals_file, ["--provider", "openai"])
    captured = capsys.readouterr().out

    assert exit_code == 0
    assert "signals=2 selected_events=2" in captured
    assert "SIGNAL pass_count value=2 events=2" in captured
    assert 'SIGNAL pass_rate value={"denominator":1,"numerator":1} events=2' in captured


def test_output_deterministic_across_runs(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    signals_file = _write_signals(tmp_path / "signals.json")
    _seed_events(event_file)

    assert _run_summary(event_file, signals_file, ["--provider", "openai"]) == 0
    first = capsys.readouterr().out
    assert _run_summary(event_file, signals_file, ["--provider", "openai"]) == 0
    second = capsys.readouterr().out
    assert first == second


def test_missing_invalid_signals_file_exit_2(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)
    missing = str(tmp_path / "missing.json")
    exit_code = _run_summary(event_file, missing)
    captured = capsys.readouterr().out
    assert exit_code == 2
    assert "MONITOR SUMMARY ERROR" in captured


def test_missing_invalid_event_file_exit_2(tmp_path: Path, capsys) -> None:
    signals_file = _write_signals(tmp_path / "signals.json")
    missing_event = str(tmp_path / "missing.jsonl")
    exit_code = _run_summary(missing_event, signals_file)
    captured = capsys.readouterr().out
    assert exit_code == 2
    assert "MONITOR SUMMARY ERROR" in captured


def test_successful_summary_exit_0(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    signals_file = _write_signals(tmp_path / "signals.json")
    _seed_events(event_file)
    exit_code = _run_summary(event_file, signals_file)
    _ = capsys.readouterr()
    assert exit_code == 0
