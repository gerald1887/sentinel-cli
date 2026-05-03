"""Monitor integration tests for monitor inspect CLI."""

from __future__ import annotations

from pathlib import Path

from sentinel.cli import main
from sentinel.monitor.event_store import append_event
from sentinel.monitor.types import EVENT_VERSION, Event


def _event(
    event_id: str,
    timestamp_utc: str,
    command: str,
    provider: str | None,
    model: str | None,
    event_type: str,
    case_id: str | None,
    status: str,
) -> Event:
    return Event(
        event_version=EVENT_VERSION,
        event_id=event_id,
        event_type=event_type,
        timestamp_utc=timestamp_utc,
        command=command,
        provider=provider,
        model=model,
        suite_case_id=case_id,
        status=status,
        exit_code=0,
        duration_ms=1,
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


def _seed_events(event_file: str) -> None:
    assert append_event(
        event_file,
        _event("e1", "2026-01-01T00:00:00Z", "run", "openai", "m1", "contract.run", "c1", "PASS"),
    ) is None
    assert append_event(
        event_file,
        _event("e2", "2026-01-02T00:00:00Z", "test", "anthropic", "m2", "guard.check", "c2", "FAIL"),
    ) is None
    assert append_event(
        event_file,
        _event("e3", "2026-01-03T00:00:00Z", "run", "openai", "m1", "contract.run", "c3", "PASS"),
    ) is None


def _run_inspect(event_file: str, args: list[str] | None = None) -> int:
    argv = ["monitor", "inspect", "--event-file", event_file]
    if args:
        argv.extend(args)
    return main(argv)


def test_inspect_without_filters_lists_events_in_append_order(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)

    exit_code = _run_inspect(event_file)
    captured = capsys.readouterr()

    assert exit_code == 0
    lines = [line for line in captured.out.splitlines() if line]
    assert len(lines) == 3
    assert '"event_id":"e1"' in lines[0]
    assert '"event_id":"e2"' in lines[1]
    assert '"event_id":"e3"' in lines[2]


def test_inspect_with_filters_returns_only_matching_events(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)

    exit_code = _run_inspect(event_file, ["--provider", "openai", "--status", "PASS"])
    captured = capsys.readouterr()

    assert exit_code == 0
    lines = [line for line in captured.out.splitlines() if line]
    assert len(lines) == 2
    assert '"event_id":"e1"' in lines[0]
    assert '"event_id":"e3"' in lines[1]


def test_inspect_with_last_returns_final_n_after_filtering(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)

    exit_code = _run_inspect(event_file, ["--command", "run", "--last", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    lines = [line for line in captured.out.splitlines() if line]
    assert len(lines) == 1
    assert '"event_id":"e3"' in lines[0]


def test_missing_invalid_event_file_returns_exit_2(tmp_path: Path, capsys) -> None:
    missing = str(tmp_path / "missing.jsonl")
    exit_code = _run_inspect(missing)
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "MONITOR INSPECT ERROR" in captured.out


def test_successful_inspect_returns_exit_0(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)

    exit_code = _run_inspect(event_file, ["--event-type", "contract.run"])
    _ = capsys.readouterr()
    assert exit_code == 0


def test_output_is_deterministic_across_repeated_runs(tmp_path: Path, capsys) -> None:
    event_file = str(tmp_path / "events.jsonl")
    _seed_events(event_file)

    assert _run_inspect(event_file, ["--provider", "openai"]) == 0
    first = capsys.readouterr().out
    assert _run_inspect(event_file, ["--provider", "openai"]) == 0
    second = capsys.readouterr().out
    assert first == second
