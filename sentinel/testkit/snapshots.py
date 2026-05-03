"""Regression snapshot path resolution and JSON read/write helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sentinel.core.errors import SentinelError, file_not_found, file_read_error

SNAPSHOT_INVALID = "SNAPSHOT_INVALID"


def resolve_snapshot_path(suite_path: str, case_id: str) -> str:
    """Resolve deterministic snapshot file path for a suite case."""
    suite_dir = Path(suite_path).resolve().parent
    return str(suite_dir / "snapshots" / f"{case_id}.json")


def read_snapshot(snapshot_path: str) -> object | SentinelError:
    """Read approved-output snapshot JSON from disk."""
    if not os.path.exists(snapshot_path):
        return file_not_found(snapshot_path)

    try:
        with open(snapshot_path, encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:  # noqa: BLE001
        return file_read_error(snapshot_path, str(exc))

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return SentinelError(
            category=SNAPSHOT_INVALID,
            code="SENTINEL_SNAPSHOT_INVALID_JSON",
            message="Snapshot file is not valid JSON.",
            details={"path": snapshot_path, "error": str(exc)},
        )


def write_snapshot(snapshot_path: str, approved_output: object) -> SentinelError | None:
    """Write approved-output snapshot JSON to disk deterministically."""
    try:
        target = Path(snapshot_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(approved_output, indent=2, sort_keys=True) + "\n"
        target.write_text(encoded, encoding="utf-8")
        return None
    except Exception as exc:  # noqa: BLE001
        return file_read_error(snapshot_path, str(exc))

