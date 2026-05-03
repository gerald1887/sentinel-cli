"""Monitor unit tests: event model/store behavior."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from sentinel.monitor import event_mapper
from sentinel.monitor.event_store import append_event, read_events
from sentinel.monitor.types import EVENT_VERSION, Event, validate_event


def _event() -> Event:
    return Event(
        event_version=EVENT_VERSION,
        event_id="evt_001",
        event_type="contract.run",
        timestamp_utc="2026-01-01T00:00:00Z",
        command="run",
        provider=None,
        model=None,
        suite_case_id=None,
        status="PASS",
        exit_code=0,
        duration_ms=100,
        contract_status=None,
        guard_status=None,
        drift_status=None,
        error_category=None,
        error_code=None,
        refusal_detected=None,
        input_tokens=None,
        output_tokens=None,
        total_tokens=None,
        artifact_refs={"source": "artifact.json"},
        metadata=None,
    )


def test_valid_event_accepted() -> None:
    event = _event()
    assert validate_event(event) is None


def test_missing_required_field_fails() -> None:
    event = replace(_event(), event_type="")
    err = validate_event(event)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"


def test_wrong_type_fails() -> None:
    event = replace(_event(), exit_code="0")  # type: ignore[arg-type]
    err = validate_event(event)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"


def test_integer_fields_accept_int_but_reject_bool() -> None:
    ok = replace(_event(), exit_code=1, duration_ms=200, input_tokens=10, output_tokens=20, total_tokens=30)
    assert validate_event(ok) is None

    bad_exit = replace(_event(), exit_code=True)  # type: ignore[arg-type]
    err = validate_event(bad_exit)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"

    bad_duration = replace(_event(), duration_ms=False)  # type: ignore[arg-type]
    err = validate_event(bad_duration)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"

    bad_input = replace(_event(), input_tokens=True)  # type: ignore[arg-type]
    err = validate_event(bad_input)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"

    bad_output = replace(_event(), output_tokens=False)  # type: ignore[arg-type]
    err = validate_event(bad_output)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"

    bad_total = replace(_event(), total_tokens=True)  # type: ignore[arg-type]
    err = validate_event(bad_total)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"


def test_metadata_none_passes() -> None:
    event = replace(_event(), metadata=None)
    assert validate_event(event) is None


def test_metadata_flat_scalar_values_passes() -> None:
    event = replace(
        _event(),
        metadata={"attempt": 1, "note": "ok", "latency_ms": 10.5, "safe": True, "optional": None},
    )
    assert validate_event(event) is None


def test_metadata_nested_object_fails() -> None:
    event = replace(_event(), metadata={"nested": {"bad": "value"}})
    err = validate_event(event)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"


def test_metadata_list_value_fails() -> None:
    event = replace(_event(), metadata={"items": ["bad"]})
    err = validate_event(event)
    assert err is not None
    assert err.code == "SENTINEL_EVENT_INVALID"


def test_append_writes_one_json_object_per_line(tmp_path: Path) -> None:
    event_file = tmp_path / "events.jsonl"
    event = _event()

    err = append_event(str(event_file), event)
    assert err is None

    text = event_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["event_id"] == "evt_001"
    assert parsed["event_version"] == EVENT_VERSION
    assert parsed["event_type"] == "contract.run"
    assert parsed["artifact_refs"] == {"source": "artifact.json"}


def test_read_fails_on_invalid_json_line(tmp_path: Path) -> None:
    event_file = tmp_path / "events.jsonl"
    event_file.write_text(
        '{"event_version":"1.0","event_id":"1","event_type":"x","timestamp_utc":"2026-01-01T00:00:00Z",'
        '"command":"run","provider":null,"model":null,"suite_case_id":null,"status":"PASS","exit_code":0,'
        '"duration_ms":1,"contract_status":null,"guard_status":null,"drift_status":null,"error_category":null,'
        '"error_code":null,"refusal_detected":null,"input_tokens":null,"output_tokens":null,"total_tokens":null,'
        '"artifact_refs":{"source":"s"},"metadata":null}\n{bad}\n',
        encoding="utf-8",
    )

    result = read_events(str(event_file))
    assert not isinstance(result, list)
    assert result.code == "SENTINEL_EVENT_STORE_INVALID_JSONL"


def test_read_fails_on_partial_truncated_line(tmp_path: Path) -> None:
    event_file = tmp_path / "events.jsonl"
    event_file.write_text('{"event_version":"1.0","event_id":"1"', encoding="utf-8")

    result = read_events(str(event_file))
    assert not isinstance(result, list)
    assert result.code == "SENTINEL_EVENT_STORE_TRUNCATED_LINE"


def test_append_preserves_file_order(tmp_path: Path) -> None:
    event_file = tmp_path / "events.jsonl"
    first = replace(_event(), event_id="evt_001", event_type="a")
    second = replace(_event(), event_id="evt_002", event_type="b")

    assert append_event(str(event_file), first) is None
    assert append_event(str(event_file), second) is None

    result = read_events(str(event_file))
    assert isinstance(result, list)
    assert [event.event_type for event in result] == ["a", "b"]


def test_read_validates_full_schema(tmp_path: Path) -> None:
    event_file = tmp_path / "events.jsonl"
    bad = {
        "event_version": "1.0",
        "event_id": "evt",
        "event_type": "contract.run",
        "timestamp_utc": "2026-01-01T00:00:00Z",
        "command": "run",
        "provider": None,
        "model": None,
        "suite_case_id": None,
        "status": "PASS",
        "exit_code": "0",
        "duration_ms": 1,
        "contract_status": None,
        "guard_status": None,
        "drift_status": None,
        "error_category": None,
        "error_code": None,
        "refusal_detected": None,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "artifact_refs": {"source": "s"},
        "metadata": None,
    }
    event_file.write_text(f"{json.dumps(bad, sort_keys=True)}\n", encoding="utf-8")
    result = read_events(str(event_file))
    assert not isinstance(result, list)
    assert result.code == "SENTINEL_EVENT_INVALID"


def test_event_timestamp_id_generation_is_test_safe(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(event_mapper, "_utc_now_iso8601", lambda: "2026-03-05T08:30:00Z")
    monkeypatch.setattr(event_mapper, "_new_event_id", lambda source_path, event_type, timestamp_utc: "evt-fixed")

    source_path = tmp_path / "source.json"
    source_path.write_text(
        json.dumps({"command": "run", "status": "PASS", "exit_code": 0, "duration_ms": 7}, sort_keys=True),
        encoding="utf-8",
    )
    mapped = event_mapper.map_source_artifact_to_event(str(source_path), "contract.run")
    assert isinstance(mapped, Event)
    assert mapped.timestamp_utc == "2026-03-05T08:30:00Z"
    assert mapped.event_id == "evt-fixed"


def test_source_integer_fields_reject_bool_in_mapper(tmp_path: Path) -> None:
    path = tmp_path / "source_bool.json"

    # Required integer field: exit_code
    path.write_text(
        json.dumps({"command": "run", "status": "PASS", "exit_code": True, "duration_ms": 10}, sort_keys=True),
        encoding="utf-8",
    )
    result = event_mapper.map_source_artifact_to_event(str(path), "contract.run")
    assert not isinstance(result, Event)
    assert result.code == "SENTINEL_EVENT_SOURCE_INVALID"

    # Required integer field: duration_ms
    path.write_text(
        json.dumps({"command": "run", "status": "PASS", "exit_code": 0, "duration_ms": False}, sort_keys=True),
        encoding="utf-8",
    )
    result = event_mapper.map_source_artifact_to_event(str(path), "contract.run")
    assert not isinstance(result, Event)
    assert result.code == "SENTINEL_EVENT_SOURCE_INVALID"

    # Nullable integer fields
    path.write_text(
        json.dumps(
            {
                "command": "run",
                "status": "PASS",
                "exit_code": 0,
                "duration_ms": 10,
                "input_tokens": True,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    result = event_mapper.map_source_artifact_to_event(str(path), "contract.run")
    assert not isinstance(result, Event)
    assert result.code == "SENTINEL_EVENT_SOURCE_INVALID"
