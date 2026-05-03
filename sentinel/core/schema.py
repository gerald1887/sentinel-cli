"""JSON-Schema validation utilities for Sentinel (Draft 2020-12).

All public functions return ``SentinelError | None`` — no exceptions leak.
"""

from __future__ import annotations

import jsonschema
from jsonschema import Draft202012Validator

from sentinel.core.errors import (
    SCHEMA_INVALID,
    SCHEMA_VALIDATION_ERROR,
    SentinelError,
)


def validate_schema_structure(schema: dict | list) -> SentinelError | None:
    """Check that *schema* is itself a valid Draft 2020-12 JSON Schema.

    Returns
    -------
    None
        Schema is structurally valid.
    SentinelError
        Schema is invalid (category ``SCHEMA_INVALID``).
    """
    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        return SentinelError(
            category=SCHEMA_INVALID,
            code="SENTINEL_SCHEMA_INVALID_STRUCTURE",
            message="Schema is not a valid Draft 2020-12 schema.",
            details={"error": str(exc.message)},
        )
    return None


def validate_instance(
    instance: object,
    schema: dict | list,
) -> SentinelError | None:
    """Validate *instance* against *schema* using Draft 2020-12.

    Returns
    -------
    None
        Instance satisfies the schema.
    SentinelError
        Validation failed (category ``SCHEMA_VALIDATION_ERROR``).
        Only the **first** error is reported.
    """
    validator = Draft202012Validator(schema)
    try:
        validator.validate(instance)
    except jsonschema.ValidationError as exc:
        return SentinelError(
            category=SCHEMA_VALIDATION_ERROR,
            code="SENTINEL_SCHEMA_VALIDATION_FAILED",
            message="Instance does not satisfy schema.",
            details={
                "error": exc.message,
                "path": list(exc.absolute_path),
                "schema_path": list(exc.absolute_schema_path),
            },
        )
    return None
