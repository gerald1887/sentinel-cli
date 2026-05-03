"""Monitor monitor event types and strict validators."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sentinel.core.errors import SCHEMA_INVALID, SentinelError

EVENT_VERSION = "1.0"


@dataclass(frozen=True, slots=True)
class Event:
    """Fixed monitor event model for Monitor integration milestone."""

    event_version: str
    event_id: str
    event_type: str
    timestamp_utc: str
    command: str
    provider: str | None
    model: str | None
    suite_case_id: str | None
    status: str
    exit_code: int
    duration_ms: int
    contract_status: str | None
    guard_status: str | None
    drift_status: str | None
    error_category: str | None
    error_code: str | None
    refusal_detected: bool | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    artifact_refs: dict[str, object] | None
    metadata: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class SignalDefinition:
    """Configured deterministic signal definition."""

    name: str
    type: str
    options: dict[str, object]
    scope: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class SignalResult:
    """Computed signal value for selected events."""

    name: str
    value: object
    event_count: int
    scope: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    """Configured deterministic rule definition."""

    id: str
    signal: str
    operator: str
    expected: object
    message: str
    scope: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Evaluated rule result."""

    id: str
    signal: str
    expected: object
    actual: object
    operator: str
    status: str
    message: str
    event_count: int


@dataclass(frozen=True, slots=True)
class MonitorCheckResult:
    """Monitor check aggregate output."""

    summary: dict[str, int]
    rules: list[RuleResult]
    signals: list[SignalResult]
    selection: dict[str, object]


def validate_event(event: Event) -> SentinelError | None:
    """Validate full Event schema and strict field types."""
    return validate_event_dict(asdict(event))


def validate_event_dict(event_obj: dict[str, object]) -> SentinelError | None:
    """Validate full Event schema from a plain dict."""
    expected_fields = {
        "event_version",
        "event_id",
        "event_type",
        "timestamp_utc",
        "command",
        "provider",
        "model",
        "suite_case_id",
        "status",
        "exit_code",
        "duration_ms",
        "contract_status",
        "guard_status",
        "drift_status",
        "error_category",
        "error_code",
        "refusal_detected",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "artifact_refs",
        "metadata",
    }
    if set(event_obj.keys()) != expected_fields:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_INVALID",
            message="Event fields do not match fixed schema.",
        )

    return _validate_event_fields(event_obj)


def _validate_event_fields(event_obj: dict[str, object]) -> SentinelError | None:
    required_string_fields = ("event_version", "event_id", "event_type", "timestamp_utc", "command", "status")
    for field in required_string_fields:
        value = event_obj[field]
        if not isinstance(value, str) or not value.strip():
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_EVENT_INVALID",
                message=f"Field '{field}' must be a non-empty string.",
            )

    if event_obj["event_version"] != EVENT_VERSION:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_INVALID",
            message=f"Field 'event_version' must be '{EVENT_VERSION}'.",
        )

    if not str(event_obj["timestamp_utc"]).endswith("Z"):
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_INVALID",
            message="Field 'timestamp_utc' must be an ISO-8601 UTC string.",
        )

    for field in ("exit_code", "duration_ms"):
        value = event_obj[field]
        if not isinstance(value, int) or isinstance(value, bool):
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_EVENT_INVALID",
                message=f"Field '{field}' must be an integer.",
            )

    nullable_strings = (
        "provider",
        "model",
        "suite_case_id",
        "contract_status",
        "guard_status",
        "drift_status",
        "error_category",
        "error_code",
    )
    for field in nullable_strings:
        value = event_obj[field]
        if value is not None and not isinstance(value, str):
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_EVENT_INVALID",
                message=f"Field '{field}' must be a string or null.",
            )

    nullable_ints = ("input_tokens", "output_tokens", "total_tokens")
    for field in nullable_ints:
        value = event_obj[field]
        if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_EVENT_INVALID",
                message=f"Field '{field}' must be an integer or null.",
            )

    refusal_detected = event_obj["refusal_detected"]
    if refusal_detected is not None and not isinstance(refusal_detected, bool):
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_INVALID",
            message="Field 'refusal_detected' must be a boolean or null.",
        )

    for field in ("artifact_refs", "metadata"):
        value = event_obj[field]
        if value is not None and not isinstance(value, dict):
            return SentinelError(
                category=SCHEMA_INVALID,
                code="SENTINEL_EVENT_INVALID",
                message=f"Field '{field}' must be an object or null.",
            )

    metadata = event_obj["metadata"]
    if metadata is not None:
        for key, value in metadata.items():
            if not isinstance(key, str):
                return SentinelError(
                    category=SCHEMA_INVALID,
                    code="SENTINEL_EVENT_INVALID",
                    message="Field 'metadata' must contain string keys only.",
                )
            if isinstance(value, (dict, list, tuple, set)):
                return SentinelError(
                    category=SCHEMA_INVALID,
                    code="SENTINEL_EVENT_INVALID",
                    message="Field 'metadata' values must be flat scalar values only.",
                )
            if value is not None and not isinstance(value, (str, int, float, bool)):
                return SentinelError(
                    category=SCHEMA_INVALID,
                    code="SENTINEL_EVENT_INVALID",
                    message="Field 'metadata' values must be flat scalar values only.",
                )

    return None
