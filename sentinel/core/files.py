"""File-loading utilities for Sentinel.

Provides deterministic, error-returning loaders for prompt (plain-text)
and schema (JSON) files.  No exceptions leak; every failure path returns
a :class:`~sentinel.core.errors.SentinelError`.
"""

from __future__ import annotations

import json
import os

from sentinel.core.errors import (
    SCHEMA_INVALID,
    SentinelError,
    file_not_found,
    file_read_error,
)


def load_prompt(path: str) -> str | SentinelError:
    """Load a prompt file as UTF-8 plain text.

    Parameters
    ----------
    path:
        Filesystem path to the prompt file.

    Returns
    -------
    str
        The raw file content (unmodified, not stripped).
    SentinelError
        On missing file, permission error, or any other I/O failure.
    """
    if not os.path.exists(path):
        return file_not_found(path)

    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception as exc:  # noqa: BLE001
        return file_read_error(path, str(exc))


def load_schema(path: str) -> dict | list | SentinelError:
    """Load and JSON-parse a schema file.

    Parameters
    ----------
    path:
        Filesystem path to the JSON schema file.

    Returns
    -------
    dict | list
        The parsed JSON object (no draft validation is performed).
    SentinelError
        On missing file, read error, or invalid JSON.
    """
    if not os.path.exists(path):
        return file_not_found(path)

    try:
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
    except Exception as exc:  # noqa: BLE001
        return file_read_error(path, str(exc))

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_SCHEMA_INVALID_JSON",
            message="Schema is not valid JSON.",
            details={"path": path, "error": str(exc)},
        )
