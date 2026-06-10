"""Structured error model and exit-code constants for Sentinel.

All errors are represented as :class:`SentinelError` dataclass instances.
Rendering is deterministic: no timestamps, no secrets, stable key order.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Exit codes (locked)
# ---------------------------------------------------------------------------

EXIT_PASS: int = 0
"""Run completed successfully – contract satisfied."""

EXIT_CONTRACT_FAIL: int = 1
"""Contract failure (invalid JSON or schema violation)."""

EXIT_ERROR: int = 2
"""Execution / system error (I/O, timeout, internal bug, …)."""

# ---------------------------------------------------------------------------
# Error categories
# ---------------------------------------------------------------------------

FILE_NOT_FOUND: str = "FILE_NOT_FOUND"
FILE_READ_ERROR: str = "FILE_READ_ERROR"
SCHEMA_INVALID: str = "SCHEMA_INVALID"
JSON_PARSE_ERROR: str = "JSON_PARSE_ERROR"
SCHEMA_VALIDATION_ERROR: str = "SCHEMA_VALIDATION_ERROR"
INTERNAL_ERROR: str = "INTERNAL_ERROR"

# Provider-related categories (constants only – no provider code).
PROVIDER_ERROR: str = "PROVIDER_ERROR"
PROVIDER_TIMEOUT: str = "PROVIDER_TIMEOUT"


# ---------------------------------------------------------------------------
# Structured error
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class SentinelError:
    """Immutable, structured representation of a single Sentinel error."""

    category: str
    """Upper-case error category (e.g. ``FILE_NOT_FOUND``)."""

    code: str
    """Machine-readable code (e.g. ``SENTINEL_FILE_NOT_FOUND``)."""

    message: str
    """Human-readable explanation."""

    location: str | None = None
    """Optional location context (file path, JSON-pointer, …)."""

    details: dict[str, object] | None = field(default=None, repr=False)
    """Optional structured details (rendered with sorted keys)."""


# ---------------------------------------------------------------------------
# Helper constructors
# ---------------------------------------------------------------------------

def file_not_found(path: str) -> SentinelError:
    """Create a :data:`FILE_NOT_FOUND` error for *path*."""
    return SentinelError(
        category=FILE_NOT_FOUND,
        code="SENTINEL_FILE_NOT_FOUND",
        message="File not found.",
        location=path,
    )


def file_read_error(path: str, reason: str) -> SentinelError:
    """Create a :data:`FILE_READ_ERROR` error for *path*."""
    return SentinelError(
        category=FILE_READ_ERROR,
        code="SENTINEL_FILE_READ_ERROR",
        message=reason,
        location=path,
    )


# ---------------------------------------------------------------------------
# Deterministic renderer
# ---------------------------------------------------------------------------

def render_error(err: SentinelError) -> str:
    """Render *err* as a single, deterministic, human-readable line.

    Format
    ------
    ``CATEGORY [CODE] location=LOC message=MSG details={k1=v1, k2=v2}``

    * ``location`` is omitted when *None*.
    * ``details`` is omitted when *None* or empty; keys are sorted.
    * No timestamps, no secrets.
    """
    parts: list[str] = [f"{err.category} [{err.code}]"]

    if err.location is not None:
        parts.append(f"location={err.location}")

    parts.append(f"message={err.message}")

    if err.details:
        rendered = ", ".join(
            f"{k}={err.details[k]}" for k in sorted(err.details)
        )
        parts.append(f"details={{{rendered}}}")

    return " ".join(parts)
