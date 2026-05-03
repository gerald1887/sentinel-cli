"""Unit tests for sentinel.core.errors – structured error model & exit codes.

Requirements trace:
    # REQ-F-010  – Structured error messages.
    # REQ-F-011  – Includes category + explanation + location when present.
    # REQ-F-014  – Exit-code model constant for contract failure (1).
    # REQ-F-015  – Exit-code model constant for execution error (2).
    # REQ-CLI-003 / REQ-F-013 – Exit-code 0 constant exists (PASS).

We validate the constants, constructors, and deterministic rendering.
No provider logic is exercised.
"""

from __future__ import annotations

from sentinel.core.errors import (
    EXIT_CONTRACT_FAIL,
    EXIT_DRIFT_DETECTED,
    EXIT_ERROR,
    EXIT_PASS,
    FILE_NOT_FOUND,
    FILE_READ_ERROR,
    SentinelError,
    file_not_found,
    file_read_error,
    render_error,
)


# REQ-F-014 / REQ-F-015 / REQ-CLI-003 / REQ-F-013
class TestExitCodes:
    """Exit-code constants include 0–3 for pass, contract fail, error, drift (reserved)."""

    def test_exit_pass_is_zero(self) -> None:
        # REQ-CLI-003 / REQ-F-013 (exit code 0 constant exists)
        assert EXIT_PASS == 0

    def test_exit_contract_fail_is_one(self) -> None:
        # REQ-F-014 (contract failure exit code)
        assert EXIT_CONTRACT_FAIL == 1

    def test_exit_error_is_two(self) -> None:
        # REQ-F-015 (execution/system error exit code)
        assert EXIT_ERROR == 2

    def test_exit_drift_detected_is_three(self) -> None:
        assert EXIT_DRIFT_DETECTED == 3

    def test_exit_codes_are_distinct(self) -> None:
        assert len({EXIT_PASS, EXIT_CONTRACT_FAIL, EXIT_ERROR, EXIT_DRIFT_DETECTED}) == 4


# REQ-F-010
class TestSentinelErrorDataclass:
    """SentinelError must carry category, code, message, and optional fields."""

    def test_required_fields(self) -> None:
        # REQ-F-010 (structured error messages)
        err = SentinelError(
            category=FILE_NOT_FOUND,
            code="SENTINEL_FILE_NOT_FOUND",
            message="File not found.",
        )
        assert err.category == FILE_NOT_FOUND
        assert err.code == "SENTINEL_FILE_NOT_FOUND"
        assert err.message == "File not found."
        assert err.location is None
        assert err.details is None

    def test_optional_fields(self) -> None:
        # REQ-F-011 (includes location when present)
        err = SentinelError(
            category=FILE_READ_ERROR,
            code="SENTINEL_FILE_READ_ERROR",
            message="Permission denied.",
            location="/etc/shadow",
            details={"errno": 13},
        )
        assert err.location == "/etc/shadow"
        assert err.details == {"errno": 13}

    def test_frozen(self) -> None:
        err = file_not_found("/tmp/missing.txt")
        try:
            err.category = "OTHER"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised, "SentinelError must be frozen (immutable)"


# REQ-F-010
class TestHelperConstructors:
    """Helper factory functions must produce correct SentinelError instances."""

    def test_file_not_found(self) -> None:
        err = file_not_found("/tmp/prompt.txt")
        assert err.category == FILE_NOT_FOUND
        assert err.code == "SENTINEL_FILE_NOT_FOUND"
        assert err.location == "/tmp/prompt.txt"

    def test_file_read_error(self) -> None:
        err = file_read_error("/tmp/schema.json", "Permission denied")
        assert err.category == FILE_READ_ERROR
        assert err.code == "SENTINEL_FILE_READ_ERROR"
        assert err.message == "Permission denied"
        assert err.location == "/tmp/schema.json"


# REQ-F-010 / REQ-F-011
class TestRenderError:
    """render_error must produce a deterministic, stable, single-line string."""

    def test_minimal_render(self) -> None:
        # REQ-F-010 (structured error messages)
        err = SentinelError(
            category="INTERNAL_ERROR",
            code="SENTINEL_INTERNAL",
            message="Something broke.",
        )
        result = render_error(err)
        assert result == "INTERNAL_ERROR [SENTINEL_INTERNAL] message=Something broke."

    def test_render_with_location(self) -> None:
        # REQ-F-011 (includes location when present)
        err = file_not_found("/abs/prompt.txt")
        result = render_error(err)
        assert "location=/abs/prompt.txt" in result
        assert result.startswith("FILE_NOT_FOUND [SENTINEL_FILE_NOT_FOUND]")

    def test_render_with_details_sorted_keys(self) -> None:
        # REQ-F-010 (details rendered with sorted keys)
        err = SentinelError(
            category="SCHEMA_INVALID",
            code="SENTINEL_SCHEMA_INVALID",
            message="Bad schema.",
            details={"z_key": "last", "a_key": "first", "m_key": "middle"},
        )
        result = render_error(err)
        assert "details={a_key=first, m_key=middle, z_key=last}" in result

    def test_deterministic_across_calls(self) -> None:
        # REQ-F-010 (same error renders identical string every time)
        err = SentinelError(
            category=FILE_NOT_FOUND,
            code="SENTINEL_FILE_NOT_FOUND",
            message="File not found.",
            location="/some/path",
            details={"hint": "check spelling"},
        )
        first = render_error(err)
        second = render_error(err)
        third = render_error(err)
        assert first == second == third

    def test_empty_details_omitted(self) -> None:
        err = SentinelError(
            category="INTERNAL_ERROR",
            code="SENTINEL_INTERNAL",
            message="Oops.",
            details={},
        )
        result = render_error(err)
        assert "details=" not in result

    def test_none_details_omitted(self) -> None:
        err = SentinelError(
            category="INTERNAL_ERROR",
            code="SENTINEL_INTERNAL",
            message="Oops.",
            details=None,
        )
        result = render_error(err)
        assert "details=" not in result

    def test_full_render_format(self) -> None:
        # REQ-F-011 (category + explanation + location)
        err = SentinelError(
            category=FILE_NOT_FOUND,
            code="SENTINEL_FILE_NOT_FOUND",
            message="Prompt file not found.",
            location="/abs/or/rel",
        )
        expected = (
            "FILE_NOT_FOUND [SENTINEL_FILE_NOT_FOUND] "
            "location=/abs/or/rel "
            "message=Prompt file not found."
        )
        assert render_error(err) == expected
