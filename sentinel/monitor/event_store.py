"""Append-only JSONL event storage for monitor events."""

from __future__ import annotations

import json
from dataclasses import asdict

from sentinel.core.errors import FILE_READ_ERROR, INTERNAL_ERROR, JSON_PARSE_ERROR, SentinelError
from sentinel.monitor.types import Event, validate_event, validate_event_dict


def append_event(event_file: str, event: Event) -> SentinelError | None:
    """Append one event as one JSON object line."""
    validation_err = validate_event(event)
    if validation_err is not None:
        return validation_err

    serialized = json.dumps(asdict(event), sort_keys=True, separators=(",", ":"))
    try:
        with open(event_file, "a", encoding="utf-8") as out_file:
            out_file.write(f"{serialized}\n")
    except Exception as exc:  # noqa: BLE001
        return SentinelError(
            category=INTERNAL_ERROR,
            code="SENTINEL_EVENT_STORE_WRITE_ERROR",
            message="Failed to append event.",
            location=event_file,
            details={"error": str(exc)},
        )
    return None


def read_events(event_file: str) -> list[Event] | SentinelError:
    """Read events from JSONL in deterministic order."""
    try:
        with open(event_file, "r", encoding="utf-8") as in_file:
            lines = in_file.readlines()
    except Exception as exc:  # noqa: BLE001
        return SentinelError(
            category=FILE_READ_ERROR,
            code="SENTINEL_EVENT_STORE_READ_ERROR",
            message="Failed to read event file.",
            location=event_file,
            details={"error": str(exc)},
        )

    if lines and not lines[-1].endswith("\n"):
        return SentinelError(
            category=JSON_PARSE_ERROR,
            code="SENTINEL_EVENT_STORE_TRUNCATED_LINE",
            message="Event file contains a partial/truncated line.",
            location=event_file,
        )

    events: list[Event] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n")
        if stripped == "":
            return SentinelError(
                category=JSON_PARSE_ERROR,
                code="SENTINEL_EVENT_STORE_INVALID_JSONL",
                message="Event file contains an empty line.",
                location=f"{event_file}:{index}",
            )
        try:
            parsed = json.loads(stripped)
        except Exception as exc:  # noqa: BLE001
            return SentinelError(
                category=JSON_PARSE_ERROR,
                code="SENTINEL_EVENT_STORE_INVALID_JSONL",
                message="Event file contains invalid JSON line.",
                location=f"{event_file}:{index}",
                details={"error": str(exc)},
            )
        if not isinstance(parsed, dict):
            return SentinelError(
                category=JSON_PARSE_ERROR,
                code="SENTINEL_EVENT_STORE_INVALID_JSONL",
                message="Event line root must be an object.",
                location=f"{event_file}:{index}",
            )
        validation_err = validate_event_dict(parsed)
        if validation_err is not None:
            return SentinelError(
                category=validation_err.category,
                code=validation_err.code,
                message=validation_err.message,
                location=f"{event_file}:{index}",
            )
        try:
            event = Event(**parsed)
        except Exception as exc:  # noqa: BLE001
            return SentinelError(
                category=JSON_PARSE_ERROR,
                code="SENTINEL_EVENT_STORE_INVALID_JSONL",
                message="Failed to instantiate Event from JSON line.",
                location=f"{event_file}:{index}",
                details={"error": str(exc)},
            )
        events.append(event)
    return events
