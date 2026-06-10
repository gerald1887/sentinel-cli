"""Map source artifacts into fixed monitor events."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sentinel.core.errors import FILE_READ_ERROR, SCHEMA_INVALID, SentinelError
from sentinel.monitor.types import EVENT_VERSION, Event


def map_source_artifact_to_event(source_path: str, event_type: str) -> Event | SentinelError:
    """Load and map a source artifact into a strict Event."""
    try:
        with open(source_path, encoding="utf-8") as source_file:
            artifact = json.load(source_file)
    except Exception as exc:  # noqa: BLE001
        return SentinelError(
            category=FILE_READ_ERROR,
            code="SENTINEL_EVENT_SOURCE_READ_ERROR",
            message="Failed to load source artifact.",
            location=source_path,
            details={"error": str(exc)},
        )

    if not isinstance(artifact, dict):
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_SOURCE_INVALID",
            message="Source artifact root must be an object.",
            location=source_path,
        )

    command = artifact.get("command")
    if not isinstance(command, str) or not command.strip():
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_SOURCE_INVALID",
            message="Source artifact missing required string field 'command'.",
            location=source_path,
        )

    status = artifact.get("status")
    if not isinstance(status, str) or not status.strip():
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_SOURCE_INVALID",
            message="Source artifact missing required string field 'status'.",
            location=source_path,
        )

    exit_code = artifact.get("exit_code")
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_SOURCE_INVALID",
            message="Source artifact missing required integer field 'exit_code'.",
            location=source_path,
        )

    duration_ms = artifact.get("duration_ms")
    if not isinstance(duration_ms, int) or isinstance(duration_ms, bool):
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_EVENT_SOURCE_INVALID",
            message="Source artifact missing required integer field 'duration_ms'.",
            location=source_path,
        )

    timestamp_utc = _utc_now_iso8601()
    event_id = _new_event_id(source_path=source_path, event_type=event_type, timestamp_utc=timestamp_utc)

    provider = _nullable_str(artifact.get("provider"), source_path, "provider")
    if isinstance(provider, SentinelError):
        return provider
    model = _nullable_str(artifact.get("model"), source_path, "model")
    if isinstance(model, SentinelError):
        return model
    suite_case_id = _nullable_str(artifact.get("suite_case_id"), source_path, "suite_case_id")
    if isinstance(suite_case_id, SentinelError):
        return suite_case_id
    contract_status = _nullable_str(artifact.get("contract_status"), source_path, "contract_status")
    if isinstance(contract_status, SentinelError):
        return contract_status
    guard_status = _nullable_str(artifact.get("guard_status"), source_path, "guard_status")
    if isinstance(guard_status, SentinelError):
        return guard_status
    drift_status = _nullable_str(artifact.get("drift_status"), source_path, "drift_status")
    if isinstance(drift_status, SentinelError):
        return drift_status
    error_category = _nullable_str(artifact.get("error_category"), source_path, "error_category")
    if isinstance(error_category, SentinelError):
        return error_category
    error_code = _nullable_str(artifact.get("error_code"), source_path, "error_code")
    if isinstance(error_code, SentinelError):
        return error_code
    refusal_detected = _nullable_bool(artifact.get("refusal_detected"), source_path, "refusal_detected")
    if isinstance(refusal_detected, SentinelError):
        return refusal_detected
    input_tokens = _nullable_int(artifact.get("input_tokens"), source_path, "input_tokens")
    if isinstance(input_tokens, SentinelError):
        return input_tokens
    output_tokens = _nullable_int(artifact.get("output_tokens"), source_path, "output_tokens")
    if isinstance(output_tokens, SentinelError):
        return output_tokens
    total_tokens = _nullable_int(artifact.get("total_tokens"), source_path, "total_tokens")
    if isinstance(total_tokens, SentinelError):
        return total_tokens
    artifact_refs = _nullable_dict(artifact.get("artifact_refs"), source_path, "artifact_refs", source_path)
    if isinstance(artifact_refs, SentinelError):
        return artifact_refs
    metadata = _nullable_dict(artifact.get("metadata"), source_path, "metadata", None)
    if isinstance(metadata, SentinelError):
        return metadata

    return Event(
        event_version=EVENT_VERSION,
        event_id=event_id,
        event_type=event_type,
        timestamp_utc=timestamp_utc,
        command=command,
        provider=provider,
        model=model,
        suite_case_id=suite_case_id,
        status=status,
        exit_code=exit_code,
        duration_ms=duration_ms,
        contract_status=contract_status,
        guard_status=guard_status,
        drift_status=drift_status,
        error_category=error_category,
        error_code=error_code,
        refusal_detected=refusal_detected,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        artifact_refs=artifact_refs,
        metadata=metadata,
    )


def _utc_now_iso8601() -> str:
    """Return current UTC time in deterministic ISO-8601 format."""
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_event_id(source_path: str, event_type: str, timestamp_utc: str) -> str:
    """Create deterministic event id for test-safe monkeypatching."""
    raw = f"{source_path}|{event_type}|{timestamp_utc}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _nullable_str(value: object, source_path: str, field_name: str) -> str | None | SentinelError:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return _source_field_type_error("string", value, source_path, field_name)


def _nullable_int(value: object, source_path: str, field_name: str) -> int | None | SentinelError:
    if value is None:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return _source_field_type_error("integer", value, source_path, field_name)


def _nullable_bool(value: object, source_path: str, field_name: str) -> bool | None | SentinelError:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return _source_field_type_error("boolean", value, source_path, field_name)


def _nullable_dict(
    value: object,
    source_path: str,
    field_name: str,
    fallback_source: str | None,
) -> dict[str, object] | None | SentinelError:
    if value is None:
        return {"source": fallback_source} if fallback_source is not None else None
    if isinstance(value, dict):
        return value
    return _source_field_type_error("object", value, source_path, field_name)


def _source_field_type_error(expected: str, value: object, source_path: str, field_name: str) -> SentinelError:
    return SentinelError(
        category=SCHEMA_INVALID,
        code="SENTINEL_EVENT_SOURCE_INVALID",
        message=f"Source artifact field '{field_name}' must be {expected} or null.",
        location=source_path,
        details={"actual_type": type(value).__name__},
    )
