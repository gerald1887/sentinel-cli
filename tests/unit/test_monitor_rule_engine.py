"""Monitor rule engine unit tests."""

from __future__ import annotations

import json
import os
import tempfile

from sentinel.core.errors import SentinelError
from sentinel.monitor.rule_engine import evaluate_rules, load_rule_definitions
from sentinel.monitor.signal_engine import compute_signals
from sentinel.monitor.types import EVENT_VERSION, Event, RuleDefinition, SignalDefinition


def _event(event_id: str, status: str, provider: str | None, duration_ms: int = 10) -> Event:
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
        duration_ms=duration_ms,
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


def _load_rules_obj(obj: dict[str, object]):
    with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tmp:
        tmp.write(json.dumps(obj, sort_keys=True))
        path = tmp.name
    try:
        return load_rule_definitions(path)
    finally:
        os.unlink(path)


def _signal_defs() -> list[SignalDefinition]:
    return [
        SignalDefinition(name="pass_count", type="count", options={"field": "status", "equals": "PASS"}),
        SignalDefinition(name="pass_rate", type="rate", options={"field": "status", "equals": "PASS"}),
        SignalDefinition(name="provider_dist", type="categorical", options={"field": "provider", "include_null": True}),
        SignalDefinition(name="dur_avg", type="duration", options={"field": "duration_ms", "op": "avg"}),
    ]


def test_valid_rule_config_loads_and_validates() -> None:
    loaded = _load_rules_obj(
        {"rules": [{"id": "r1", "signal": "pass_count", "operator": "gte", "expected": 1, "message": "ok"}]}
    )
    assert isinstance(loaded, list)
    assert loaded[0].id == "r1"


def test_invalid_rule_config_fails_deterministically() -> None:
    loaded = _load_rules_obj(
        {"rules": [{"id": "r1", "signal": "pass_count", "operator": "bad", "expected": 1, "message": "ok"}]}
    )
    assert not isinstance(loaded, list)
    assert loaded.code == "SENTINEL_RULE_CONFIG_INVALID"


def test_each_supported_operator_evaluates_correctly() -> None:
    events = [_event("1", "PASS", "openai"), _event("2", "FAIL", None)]
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [
        RuleDefinition("eq", "pass_count", "eq", 1, "x"),
        RuleDefinition("ne", "pass_count", "ne", 2, "x"),
        RuleDefinition("lt", "pass_count", "lt", 2, "x"),
        RuleDefinition("lte", "pass_count", "lte", 1, "x"),
        RuleDefinition("gt", "pass_count", "gt", 0, "x"),
        RuleDefinition("gte", "pass_count", "gte", 1, "x"),
        RuleDefinition("in", "pass_count", "in", [0, 1], "x"),
        RuleDefinition("not_in", "pass_count", "not_in", [2, 3], "x"),
        RuleDefinition("contains_key", "provider_dist", "contains_key", "openai", "x"),
        RuleDefinition("not_contains_key", "provider_dist", "not_contains_key", "missing", "x"),
    ]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert [rule.status for rule in result.rules] == ["PASS"] * 10


def test_missing_signal_returns_error() -> None:
    events = [_event("1", "PASS", "openai")]
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [RuleDefinition("r1", "unknown_signal", "eq", 1, "x")]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert result.rules[0].status == "ERROR"


def test_invalid_operator_for_signal_type_returns_error() -> None:
    events = [_event("1", "PASS", "openai")]
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [RuleDefinition("r1", "pass_rate", "lt", 1, "x")]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert result.rules[0].status == "ERROR"


def test_type_mismatch_returns_error_and_no_coercion() -> None:
    events = [_event("1", "PASS", "openai")]
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [RuleDefinition("r1", "pass_count", "eq", "1", "x")]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert result.rules[0].status == "ERROR"


def test_empty_selection_non_count_signal_is_error() -> None:
    events = []
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [RuleDefinition("r1", "dur_avg", "eq", 1, "x")]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert result.rules[0].status == "ERROR"


def test_rule_order_preserved() -> None:
    events = [_event("1", "PASS", "openai")]
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [
        RuleDefinition("r2", "pass_count", "gte", 1, "x"),
        RuleDefinition("r1", "pass_count", "gte", 1, "x"),
    ]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert [rule.id for rule in result.rules] == ["r2", "r1"]


def test_rule_scope_recomputes_against_scoped_events() -> None:
    events = [_event("1", "PASS", "openai"), _event("2", "FAIL", "anthropic")]
    defs = _signal_defs()
    signals = compute_signals(events, defs)
    assert isinstance(signals, list)
    rules = [
        RuleDefinition(
            "r1",
            "pass_count",
            "eq",
            1,
            "x",
            scope={"provider": "openai"},
        )
    ]
    result = evaluate_rules(events, defs, signals, rules)
    assert not isinstance(result, SentinelError)
    assert result.rules[0].status == "PASS"
    assert result.rules[0].event_count == 1
