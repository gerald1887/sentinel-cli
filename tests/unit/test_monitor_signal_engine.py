"""Monitor signal engine unit tests."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from sentinel.monitor.output import render_summary
from sentinel.monitor.signal_engine import compute_signals, load_signal_definitions
from sentinel.monitor.types import EVENT_VERSION, Event


def _event(
    event_id: str,
    status: str,
    duration_ms: int | None,
    total_tokens: int | None,
    provider: str | None,
) -> Event:
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
        duration_ms=duration_ms if duration_ms is not None else 0,
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


def _write_signal_config(path: Path, payload: dict[str, object]) -> str:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return str(path)


def test_valid_signal_config_loads_and_validates(tmp_path: Path) -> None:
    path = _write_signal_config(
        tmp_path / "signals.json",
        {"signals": [{"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}]},
    )
    loaded = load_signal_definitions(path)
    assert isinstance(loaded, list)
    assert loaded[0].name == "pass_count"


def test_invalid_config_fails_deterministically(tmp_path: Path) -> None:
    path = _write_signal_config(
        tmp_path / "signals.json",
        {"signals": [{"name": "bad", "type": "count", "options": {"field": "status"}, "extra": 1}]},
    )
    loaded = load_signal_definitions(path)
    assert not isinstance(loaded, list)
    assert loaded.code == "SENTINEL_SIGNAL_CONFIG_INVALID"


def test_each_signal_type_computes_correctly() -> None:
    events = [
        _event("1", "PASS", 10, 100, "openai"),
        _event("2", "FAIL", 20, None, "openai"),
        _event("3", "PASS", 30, 300, None),
    ]
    defs = [
        {"name": "count_pass", "type": "count", "options": {"field": "status", "equals": "PASS"}},
        {"name": "rate_pass", "type": "rate", "options": {"field": "status", "equals": "PASS"}},
        {"name": "dur_sum", "type": "duration", "options": {"field": "duration_ms", "op": "sum"}},
        {"name": "tok_avg", "type": "token", "options": {"field": "total_tokens", "op": "avg"}},
        {"name": "provider_dist", "type": "categorical", "options": {"field": "provider"}},
    ]
    loaded = load_signal_definitions_from_obj({"signals": defs})
    assert isinstance(loaded, list)
    result = compute_signals(events, loaded)
    assert isinstance(result, list)
    assert [r.value for r in result] == [2, {"denominator": 3, "numerator": 2}, 60, 200.0, {"openai": 2}]


def test_config_order_preserved() -> None:
    events = [_event("1", "PASS", 10, 1, "openai")]
    loaded = load_signal_definitions_from_obj(
        {
            "signals": [
                {"name": "second", "type": "count", "options": {"field": "status", "equals": "PASS"}},
                {"name": "first", "type": "count", "options": {"field": "status", "equals": "PASS"}},
            ]
        }
    )
    assert isinstance(loaded, list)
    result = compute_signals(events, loaded)
    assert isinstance(result, list)
    assert [r.name for r in result] == ["second", "first"]


def test_null_handling_per_type_verified() -> None:
    events = [
        _event("1", "PASS", 10, None, "openai"),
        _event("2", "FAIL", 20, 100, None),
    ]
    loaded = load_signal_definitions_from_obj(
        {
            "signals": [
                {"name": "count_status", "type": "count", "options": {"field": "provider"}},
                {"name": "rate_status", "type": "rate", "options": {"field": "provider", "equals": "openai"}},
                {"name": "token_sum", "type": "token", "options": {"field": "total_tokens", "op": "sum"}},
                {"name": "cat_default", "type": "categorical", "options": {"field": "provider"}},
                {"name": "cat_with_null", "type": "categorical", "options": {"field": "provider", "include_null": True}},
            ]
        }
    )
    assert isinstance(loaded, list)
    result = compute_signals(events, loaded)
    assert isinstance(result, list)
    assert [r.value for r in result] == [1, {"denominator": 1, "numerator": 1}, 100, {"openai": 1}, {"null": 1, "openai": 1}]


def test_no_implicit_signals_computed() -> None:
    events = [_event("1", "PASS", 10, 10, "openai")]
    loaded = load_signal_definitions_from_obj({"signals": []})
    assert isinstance(loaded, list)
    result = compute_signals(events, loaded)
    assert result == []


def test_empty_selection_behavior_deterministic() -> None:
    loaded = load_signal_definitions_from_obj(
        {
            "signals": [
                {"name": "count", "type": "count", "options": {"field": "status", "equals": "PASS"}},
                {"name": "rate", "type": "rate", "options": {"field": "status", "equals": "PASS"}},
                {"name": "duration", "type": "duration", "options": {"field": "duration_ms", "op": "avg"}},
                {"name": "token", "type": "token", "options": {"field": "total_tokens", "op": "sum"}},
                {"name": "cat", "type": "categorical", "options": {"field": "provider"}},
            ]
        }
    )
    assert isinstance(loaded, list)
    result = compute_signals([], loaded)
    assert isinstance(result, list)
    assert [r.value for r in result] == [0, {"denominator": 0, "numerator": 0}, None, None, {}]


def test_scope_filtering_inside_signal_works_correctly() -> None:
    events = [
        _event("1", "PASS", 10, 10, "openai"),
        _event("2", "PASS", 20, 20, "anthropic"),
    ]
    loaded = load_signal_definitions_from_obj(
        {
            "signals": [
                {
                    "name": "openai_pass",
                    "type": "count",
                    "options": {"field": "status", "equals": "PASS"},
                    "scope": {"provider": "openai"},
                }
            ]
        }
    )
    assert isinstance(loaded, list)
    result = compute_signals(events, loaded)
    assert isinstance(result, list)
    assert result[0].value == 1
    assert result[0].event_count == 1


def test_rate_value_representation_stable_end_to_end() -> None:
    events = [
        _event("1", "PASS", 10, 10, "openai"),
        _event("2", "FAIL", 20, 20, "openai"),
        _event("3", "PASS", 30, 30, "openai"),
    ]
    loaded = load_signal_definitions_from_obj(
        {"signals": [{"name": "pass_rate", "type": "rate", "options": {"field": "status", "equals": "PASS"}}]}
    )
    assert isinstance(loaded, list)
    result = compute_signals(events, loaded)
    assert isinstance(result, list)
    assert result[0].value == {"numerator": 2, "denominator": 3}

    rendered = render_summary(selected_event_count=3, results=result)
    assert rendered[2] == 'SIGNAL pass_rate value={"denominator":3,"numerator":2} events=3'


def load_signal_definitions_from_obj(obj: dict[str, object]):
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tmp:
        tmp.write(json.dumps(obj, sort_keys=True))
        tmp_path = tmp.name
    try:
        return load_signal_definitions(tmp_path)
    finally:
        os.unlink(tmp_path)
