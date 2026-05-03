"""Deterministic rule loading and evaluation."""

from __future__ import annotations

import json

import yaml

from sentinel.core.errors import FILE_READ_ERROR, SCHEMA_INVALID, SentinelError
from sentinel.monitor.selector import InspectFilters, select_events
from sentinel.monitor.signal_engine import compute_signals
from sentinel.monitor.types import Event, MonitorCheckResult, RuleDefinition, RuleResult, SignalDefinition, SignalResult

ALLOWED_OPERATORS = {"eq", "ne", "lt", "lte", "gt", "gte", "in", "not_in", "contains_key", "not_contains_key"}
ALLOWED_RULE_KEYS = {"id", "signal", "operator", "expected", "message", "scope"}
ALLOWED_SCOPE_KEYS = {
    "from_timestamp_utc",
    "to_timestamp_utc",
    "last",
    "command",
    "provider",
    "model",
    "event_type",
    "case_id",
    "status",
}


def load_rule_definitions(path: str) -> list[RuleDefinition] | SentinelError:
    """Load rules config with strict deterministic validation."""
    try:
        with open(path, "r", encoding="utf-8") as config_file:
            if path.endswith(".json"):
                raw = json.load(config_file)
            elif path.endswith((".yaml", ".yml")):
                raw = yaml.safe_load(config_file)
            else:
                return _rule_error("Rule config must use .json, .yaml, or .yml extension.", path)
    except Exception as exc:  # noqa: BLE001
        return SentinelError(
            category=FILE_READ_ERROR,
            code="SENTINEL_RULE_CONFIG_READ_ERROR",
            message="Failed to load rule config.",
            location=path,
            details={"error": str(exc)},
        )
    return _parse_rule_definitions(raw, path)


def evaluate_rules(
    events: list[Event],
    signal_definitions: list[SignalDefinition],
    global_signals: list[SignalResult],
    rules: list[RuleDefinition],
) -> MonitorCheckResult | SentinelError:
    """Evaluate rules in config order with deterministic semantics."""
    signal_def_by_name = {signal.name: signal for signal in signal_definitions}
    global_signal_by_name = {signal.name: signal for signal in global_signals}
    rule_results: list[RuleResult] = []
    pass_count = 0
    fail_count = 0
    error_count = 0

    for rule in rules:
        definition = signal_def_by_name.get(rule.signal)
        if definition is None:
            rule_result = RuleResult(
                id=rule.id,
                signal=rule.signal,
                expected=rule.expected,
                actual=None,
                operator=rule.operator,
                status="ERROR",
                message=f"Signal '{rule.signal}' is not defined in signals config.",
                event_count=0,
            )
            rule_results.append(rule_result)
            error_count += 1
            continue

        signal_result = global_signal_by_name.get(rule.signal)
        scoped_events = events
        if rule.scope is not None:
            scoped = select_events(events, _scope_to_filters(rule.scope))
            if isinstance(scoped, SentinelError):
                return scoped
            scoped_events = scoped
            recomputed = compute_signals(scoped_events, [definition])
            if isinstance(recomputed, SentinelError):
                return recomputed
            signal_result = recomputed[0]

        if signal_result is None:
            return _rule_error("Internal missing signal result during evaluation.")

        status, message = _evaluate_single_rule(rule, signal_result, definition.type)
        rule_result = RuleResult(
            id=rule.id,
            signal=rule.signal,
            expected=rule.expected,
            actual=signal_result.value,
            operator=rule.operator,
            status=status,
            message=message if status == "ERROR" else rule.message,
            event_count=signal_result.event_count,
        )
        rule_results.append(rule_result)
        if status == "PASS":
            pass_count += 1
        elif status == "FAIL":
            fail_count += 1
        else:
            error_count += 1

    return MonitorCheckResult(
        summary={
            "total_rules": len(rule_results),
            "pass": pass_count,
            "fail": fail_count,
            "error": error_count,
            "events": len(events),
        },
        rules=rule_results,
        signals=global_signals,
        selection={"event_count": len(events)},
    )


def _parse_rule_definitions(raw: object, path: str) -> list[RuleDefinition] | SentinelError:
    if not isinstance(raw, dict) or set(raw.keys()) != {"rules"}:
        return _rule_error("Rule config root must be an object with only 'rules'.", path)
    rules = raw["rules"]
    if not isinstance(rules, list):
        return _rule_error("Field 'rules' must be an array.", path)
    definitions: list[RuleDefinition] = []
    for index, rule in enumerate(rules, start=1):
        location = f"{path}:rules[{index}]"
        if not isinstance(rule, dict):
            return _rule_error("Each rule must be an object.", location)
        if not {"id", "signal", "operator", "expected", "message"}.issubset(rule.keys()):
            return _rule_error("Rule missing required fields.", location)
        if set(rule.keys()) - ALLOWED_RULE_KEYS:
            return _rule_error("Rule contains unknown fields.", location)
        if not isinstance(rule["id"], str) or not rule["id"].strip():
            return _rule_error("Rule 'id' must be a non-empty string.", location)
        if not isinstance(rule["signal"], str) or not rule["signal"].strip():
            return _rule_error("Rule 'signal' must be a non-empty string.", location)
        if rule["operator"] not in ALLOWED_OPERATORS:
            return _rule_error("Rule 'operator' is invalid.", location)
        if not isinstance(rule["message"], str):
            return _rule_error("Rule 'message' must be a string.", location)
        scope = rule.get("scope")
        if scope is not None:
            if not isinstance(scope, dict):
                return _rule_error("Rule 'scope' must be an object.", location)
            if set(scope.keys()) - ALLOWED_SCOPE_KEYS:
                return _rule_error("Rule 'scope' contains unknown fields.", location)
        definitions.append(
            RuleDefinition(
                id=rule["id"],
                signal=rule["signal"],
                operator=rule["operator"],
                expected=rule["expected"],
                message=rule["message"],
                scope=scope,
            )
        )
    return definitions


def _evaluate_single_rule(rule: RuleDefinition, signal: SignalResult, signal_type: str) -> tuple[str, str]:
    actual = signal.value
    expected = rule.expected
    op = rule.operator

    if signal.event_count == 0 and signal_type != "count":
        return "ERROR", "Empty event selection for non-count signal."

    if op in {"contains_key", "not_contains_key"}:
        if not isinstance(actual, dict):
            return "ERROR", "Operator requires mapping signal value."
        if not isinstance(expected, str):
            return "ERROR", "Operator requires expected string key."
        contains = expected in actual
        passed = contains if op == "contains_key" else not contains
        return ("PASS", "") if passed else ("FAIL", "")

    if op in {"lt", "lte", "gt", "gte"}:
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            return "ERROR", "Ordered operator requires numeric actual value."
        if not isinstance(expected, (int, float)) or isinstance(expected, bool):
            return "ERROR", "Ordered operator requires numeric expected value."
        if op == "lt":
            passed = actual < expected
        elif op == "lte":
            passed = actual <= expected
        elif op == "gt":
            passed = actual > expected
        else:
            passed = actual >= expected
        return ("PASS", "") if passed else ("FAIL", "")

    if op in {"eq", "ne"}:
        if type(actual) is not type(expected):
            return "ERROR", "eq/ne require exact type match."
        passed = (actual == expected) if op == "eq" else (actual != expected)
        return ("PASS", "") if passed else ("FAIL", "")

    if op in {"in", "not_in"}:
        if isinstance(expected, (str, list, tuple, set, dict)):
            member = actual in expected
        else:
            return "ERROR", "in/not_in require expected container value."
        passed = member if op == "in" else not member
        return ("PASS", "") if passed else ("FAIL", "")

    return "ERROR", "Unsupported operator."


def _scope_to_filters(scope: dict[str, object]) -> InspectFilters:
    return InspectFilters(
        from_timestamp_utc=scope.get("from_timestamp_utc"),  # type: ignore[arg-type]
        to_timestamp_utc=scope.get("to_timestamp_utc"),  # type: ignore[arg-type]
        last=scope.get("last"),  # type: ignore[arg-type]
        command=scope.get("command"),  # type: ignore[arg-type]
        provider=scope.get("provider"),  # type: ignore[arg-type]
        model=scope.get("model"),  # type: ignore[arg-type]
        event_type=scope.get("event_type"),  # type: ignore[arg-type]
        case_id=scope.get("case_id"),  # type: ignore[arg-type]
        status=scope.get("status"),  # type: ignore[arg-type]
    )


def _rule_error(message: str, location: str | None = None) -> SentinelError:
    return SentinelError(
        category=SCHEMA_INVALID,
        code="SENTINEL_RULE_CONFIG_INVALID",
        message=message,
        location=location,
    )
