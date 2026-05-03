"""Unit tests for sentinel.core.schema – Draft 2020-12 validation.

Requirements trace:
    # REQ-D-001  – Supports JSON Schema Draft 2020-12.
    # REQ-D-002  – Schema correctness check (structure validation).
    # REQ-CE-001 – Validate response against schema.
    # REQ-F-010  – Structured error messages.
    # REQ-F-012  – Deterministic output behavior.
    # REQ-F-014  – Contract failure path exists via validation error.

No provider calls.  No CLI wiring.
"""

from __future__ import annotations

from sentinel.core.errors import (
    SCHEMA_INVALID,
    SCHEMA_VALIDATION_ERROR,
    SentinelError,
)
from sentinel.core.schema import validate_instance, validate_schema_structure


# ---------------------------------------------------------------------------
# validate_schema_structure
# ---------------------------------------------------------------------------

class TestValidateSchemaStructure:
    """Schema-level Draft 2020-12 structure checks."""

    def test_validate_schema_structure_valid(self) -> None:
        # REQ-D-001 (supports JSON Schema Draft 2020-12)
        # REQ-D-002 (schema correctness check)
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        result = validate_schema_structure(schema)
        assert result is None

    def test_validate_schema_structure_valid_minimal(self) -> None:
        # REQ-D-001 (bare-minimum valid schema)
        schema: dict = {"type": "object"}
        result = validate_schema_structure(schema)
        assert result is None

    def test_validate_schema_structure_invalid(self) -> None:
        # REQ-D-002 (schema correctness check – failure path)
        schema = {"type": "not-a-real-type"}
        result = validate_schema_structure(schema)
        assert isinstance(result, SentinelError)
        assert result.category == SCHEMA_INVALID
        assert result.code == "SENTINEL_SCHEMA_INVALID_STRUCTURE"
        assert result.details is not None
        assert "error" in result.details
        assert isinstance(result.details["error"], str)
        assert len(result.details["error"]) > 0

    def test_validate_schema_structure_returns_none_or_error(self) -> None:
        # No exceptions leak
        for schema in [{"type": "string"}, {"type": 123}]:
            result = validate_schema_structure(schema)
            assert result is None or isinstance(result, SentinelError)


# ---------------------------------------------------------------------------
# validate_instance
# ---------------------------------------------------------------------------

class TestValidateInstance:
    """Instance-level validation against a schema."""

    def test_validate_instance_valid(self) -> None:
        # REQ-CE-001 (validate response against schema)
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        instance = {"name": "Alice"}
        result = validate_instance(instance, schema)
        assert result is None

    def test_validate_instance_invalid(self) -> None:
        # REQ-CE-001 (validate response against schema)
        # REQ-F-014 (contract failure path exists via validation error)
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        instance = {"name": 42}
        result = validate_instance(instance, schema)
        assert isinstance(result, SentinelError)
        assert result.category == SCHEMA_VALIDATION_ERROR
        assert result.code == "SENTINEL_SCHEMA_VALIDATION_FAILED"
        assert result.details is not None
        assert "error" in result.details
        assert "path" in result.details
        assert "schema_path" in result.details

    def test_validate_instance_missing_required(self) -> None:
        # REQ-CE-001 (missing required field is a contract violation)
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        instance: dict = {}
        result = validate_instance(instance, schema)
        assert isinstance(result, SentinelError)
        assert result.category == SCHEMA_VALIDATION_ERROR

    def test_validate_instance_returns_none_or_error(self) -> None:
        # No exceptions leak
        schema = {"type": "string"}
        for inst in ["hello", 42]:
            result = validate_instance(inst, schema)
            assert result is None or isinstance(result, SentinelError)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    """Repeated calls with the same input must produce identical errors."""

    def test_validation_error_deterministic_details(self) -> None:
        # REQ-F-010 (structured error)
        # REQ-F-012 (deterministic output behavior)
        schema = {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "string"},
            },
            "required": ["x", "y"],
        }
        instance = {"x": "wrong", "y": 999}

        first = validate_instance(instance, schema)
        second = validate_instance(instance, schema)

        assert isinstance(first, SentinelError)
        assert isinstance(second, SentinelError)
        assert first.category == second.category
        assert first.code == second.code
        assert first.message == second.message
        assert first.details == second.details

    def test_schema_structure_error_deterministic(self) -> None:
        # REQ-F-012 (deterministic output behavior)
        schema = {"type": "not-a-real-type"}

        first = validate_schema_structure(schema)
        second = validate_schema_structure(schema)

        assert isinstance(first, SentinelError)
        assert isinstance(second, SentinelError)
        assert first.details == second.details
