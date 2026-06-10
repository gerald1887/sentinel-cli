"""Deterministic signal config loading and computation."""

from __future__ import annotations

import json
from fractions import Fraction

import yaml

from sentinel.core.errors import FILE_READ_ERROR, SCHEMA_INVALID, SentinelError
from sentinel.monitor.selector import InspectFilters, select_events
from sentinel.monitor.types import Event, SignalDefinition, SignalResult

ALLOWED_SIGNAL_TYPES = {"count", "rate", "duration", "token", "categorical"}
ALLOWED_DEFINITION_KEYS = {"name", "type", "options", "scope"}
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
RATE_VALUE_NUMERATOR_KEY = "numerator"
RATE_VALUE_DENOMINATOR_KEY = "denominator"


def load_signal_definitions(path: str) -> list[SignalDefinition] | SentinelError:
    """Load and strictly validate configured signal definitions."""
    try:
        with open(path, encoding="utf-8") as config_file:
            if path.endswith(".json"):
                raw = json.load(config_file)
            elif path.endswith((".yaml", ".yml")):
                raw = yaml.safe_load(config_file)
            else:
                return SentinelError(
                    category=SCHEMA_INVALID,
                    code="SENTINEL_SIGNAL_CONFIG_INVALID",
                    message="Signal config must use .json, .yaml, or .yml extension.",
                    location=path,
                )
    except Exception as exc:  # noqa: BLE001
        return SentinelError(
            category=FILE_READ_ERROR,
            code="SENTINEL_SIGNAL_CONFIG_READ_ERROR",
            message="Failed to load signal config.",
            location=path,
            details={"error": str(exc)},
        )
    return _parse_signal_definitions(raw, path)


def compute_signals(events: list[Event], definitions: list[SignalDefinition]) -> list[SignalResult] | SentinelError:
    """Compute signals in config order over selected events."""
    results: list[SignalResult] = []
    for definition in definitions:
        scoped_events: list[Event] = events
        if definition.scope is not None:
            scoped = select_events(events, _scope_to_filters(definition.scope))
            if isinstance(scoped, SentinelError):
                return scoped
            scoped_events = scoped

        computed = _compute_signal_value(scoped_events, definition)
        if isinstance(computed, SentinelError):
            return computed
        results.append(
            SignalResult(
                name=definition.name,
                value=computed,
                event_count=len(scoped_events),
                scope=definition.scope,
            )
        )
    return results


def _parse_signal_definitions(raw: object, path: str) -> list[SignalDefinition] | SentinelError:
    if not isinstance(raw, dict) or set(raw.keys()) != {"signals"}:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_SIGNAL_CONFIG_INVALID",
            message="Signal config root must be an object with only 'signals'.",
            location=path,
        )
    signals = raw["signals"]
    if not isinstance(signals, list):
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_SIGNAL_CONFIG_INVALID",
            message="Field 'signals' must be an array.",
            location=path,
        )

    definitions: list[SignalDefinition] = []
    for index, signal in enumerate(signals, start=1):
        location = f"{path}:signals[{index}]"
        if not isinstance(signal, dict):
            return _config_error("Each signal must be an object.", location)
        if not {"name", "type", "options"}.issubset(signal.keys()):
            return _config_error("Signal missing required fields.", location)
        if set(signal.keys()) - ALLOWED_DEFINITION_KEYS:
            return _config_error("Signal contains unknown fields.", location)
        if not isinstance(signal["name"], str) or not signal["name"].strip():
            return _config_error("Signal 'name' must be a non-empty string.", location)
        if signal["type"] not in ALLOWED_SIGNAL_TYPES:
            return _config_error("Signal 'type' is invalid.", location)
        if not isinstance(signal["options"], dict):
            return _config_error("Signal 'options' must be an object.", location)
        options_error = _validate_signal_options(signal["type"], signal["options"], location)
        if options_error is not None:
            return options_error
        scope = signal.get("scope")
        if scope is not None:
            if not isinstance(scope, dict):
                return _config_error("Signal 'scope' must be an object.", location)
            unknown_scope = set(scope.keys()) - ALLOWED_SCOPE_KEYS
            if unknown_scope:
                return _config_error("Signal 'scope' contains unknown fields.", location)
        definitions.append(
            SignalDefinition(
                name=signal["name"],
                type=signal["type"],
                options=signal["options"],
                scope=scope,
            )
        )
    return definitions


def _validate_signal_options(signal_type: str, options: dict[str, object], location: str) -> SentinelError | None:
    if signal_type == "count":
        required = {"field"}
        allowed = {"field", "equals"}
    elif signal_type == "rate":
        required = {"field", "equals"}
        allowed = {"field", "equals"}
    elif signal_type in {"duration", "token"}:
        required = {"field", "op"}
        allowed = {"field", "op"}
    elif signal_type == "categorical":
        required = {"field"}
        allowed = {"field", "include_null"}
    else:
        return _config_error("Signal 'type' is invalid.", location)

    if not required.issubset(options.keys()):
        return _config_error("Signal 'options' missing required fields.", location)
    if set(options.keys()) - allowed:
        return _config_error("Signal 'options' contains unknown fields.", location)
    return None


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


def _compute_signal_value(events: list[Event], definition: SignalDefinition) -> object | SentinelError:
    if definition.type == "count":
        return _compute_count(events, definition)
    if definition.type == "rate":
        return _compute_rate(events, definition)
    if definition.type == "duration":
        return _compute_numeric(events, definition, "duration")
    if definition.type == "token":
        return _compute_numeric(events, definition, "token")
    if definition.type == "categorical":
        return _compute_categorical(events, definition)
    return SentinelError(
        category=SCHEMA_INVALID,
        code="SENTINEL_SIGNAL_CONFIG_INVALID",
        message="Unsupported signal type.",
    )


def _compute_count(events: list[Event], definition: SignalDefinition) -> int | SentinelError:
    field = definition.options.get("field")
    if not isinstance(field, str):
        return _config_error("Count signal requires string option 'field'.")
    equals = definition.options.get("equals")
    values = _get_values(events, field)
    if isinstance(values, SentinelError):
        return values
    total = 0
    for value in values:
        if value is None:
            continue
        if "equals" in definition.options and value != equals:
            continue
        total += 1
    return total


def _compute_rate(events: list[Event], definition: SignalDefinition) -> dict[str, int] | SentinelError:
    field = definition.options.get("field")
    equals = definition.options.get("equals")
    if not isinstance(field, str):
        return _config_error("Rate signal requires string option 'field'.")
    values = _get_values(events, field)
    if isinstance(values, SentinelError):
        return values
    denominator = 0
    numerator = 0
    for value in values:
        if value is None:
            continue
        denominator += 1
        if value == equals:
            numerator += 1
    return canonical_rate_value(numerator=numerator, denominator=denominator)


def canonical_rate_value(numerator: int, denominator: int) -> dict[str, int]:
    """Return canonical rate representation for SignalResult.value."""
    if denominator == 0:
        return {
            RATE_VALUE_NUMERATOR_KEY: 0,
            RATE_VALUE_DENOMINATOR_KEY: 0,
        }
    frac = Fraction(numerator, denominator)
    return {
        RATE_VALUE_NUMERATOR_KEY: frac.numerator,
        RATE_VALUE_DENOMINATOR_KEY: frac.denominator,
    }


def _compute_numeric(
    events: list[Event], definition: SignalDefinition, family: str
) -> int | float | None | SentinelError:
    field = definition.options.get("field")
    op = definition.options.get("op")
    if not isinstance(field, str):
        return _config_error(f"{family.capitalize()} signal requires string option 'field'.")
    if op not in {"sum", "avg", "min", "max"}:
        return _config_error(f"{family.capitalize()} signal requires option 'op' in sum|avg|min|max.")

    values = _get_values(events, field)
    if isinstance(values, SentinelError):
        return values
    numbers = [value for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    if op == "sum":
        return sum(numbers)
    if op == "min":
        return min(numbers)
    if op == "max":
        return max(numbers)
    return sum(numbers) / len(numbers)


def _compute_categorical(events: list[Event], definition: SignalDefinition) -> dict[str, int] | SentinelError:
    field = definition.options.get("field")
    include_null = definition.options.get("include_null", False)
    if not isinstance(field, str):
        return _config_error("Categorical signal requires string option 'field'.")
    if not isinstance(include_null, bool):
        return _config_error("Categorical signal option 'include_null' must be boolean.")

    values = _get_values(events, field)
    if isinstance(values, SentinelError):
        return values

    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            if not include_null:
                continue
            key = "null"
        else:
            key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _get_values(events: list[Event], field: str) -> list[object] | SentinelError:
    if field not in Event.__dataclass_fields__:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_SIGNAL_CONFIG_INVALID",
            message=f"Signal field '{field}' does not exist in Event schema.",
        )
    return [getattr(event, field) for event in events]


def _config_error(message: str, location: str | None = None) -> SentinelError:
    return SentinelError(
        category=SCHEMA_INVALID,
        code="SENTINEL_SIGNAL_CONFIG_INVALID",
        message=message,
        location=location,
    )
