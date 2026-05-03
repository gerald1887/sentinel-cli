"""Unit tests for sentinel.core.files – file loading with deterministic errors.

Requirements trace:
    # REQ-FS-001 – Prompt loaded from file (plain text, UTF-8).
    # REQ-FS-002 – Schema loaded from file (JSON).
    # REQ-FS-003 – Validate existence before execution.
    # REQ-FS-004 – Deterministic failure if missing or unreadable.
    # REQ-D-001 – Supports schema input (loaded as JSON; no draft validation yet).
    # REQ-D-002 – Schema correctness pre-flight (must be valid JSON).
    # REQ-D-003 – Prompt is plain-text UTF-8.
    # REQ-D-004 – Files read as UTF-8.

No provider calls.  No schema-draft validation.
"""

from __future__ import annotations

import json
from pathlib import Path

from sentinel.core.errors import (
    FILE_NOT_FOUND,
    FILE_READ_ERROR,
    SCHEMA_INVALID,
    SentinelError,
)
from sentinel.core.files import load_prompt, load_schema


# ---------------------------------------------------------------------------
# load_prompt
# ---------------------------------------------------------------------------

class TestLoadPromptSuccess:
    """Successful prompt loading."""

    def test_load_prompt_success(self, tmp_path: Path) -> None:
        # REQ-FS-001 (prompt from file, plain text)
        # REQ-D-003 (plain-text UTF-8)
        # REQ-D-004 (read as UTF-8)
        prompt_file = tmp_path / "prompt.txt"
        content = "You are a helpful assistant.\nDo the thing.\n"
        prompt_file.write_text(content, encoding="utf-8")

        result = load_prompt(str(prompt_file))

        assert isinstance(result, str)
        assert result == content

    def test_load_prompt_preserves_content_exactly(self, tmp_path: Path) -> None:
        # REQ-FS-001 (content not stripped or modified)
        prompt_file = tmp_path / "whitespace.txt"
        content = "  leading spaces\n\n  trailing too  \n\n"
        prompt_file.write_text(content, encoding="utf-8")

        result = load_prompt(str(prompt_file))

        assert isinstance(result, str)
        assert result == content

    def test_load_prompt_empty_file(self, tmp_path: Path) -> None:
        # REQ-FS-001 (empty file is still valid)
        prompt_file = tmp_path / "empty.txt"
        prompt_file.write_text("", encoding="utf-8")

        result = load_prompt(str(prompt_file))

        assert isinstance(result, str)
        assert result == ""


class TestLoadPromptMissing:
    """Missing prompt file returns FILE_NOT_FOUND."""

    def test_load_prompt_missing_file(self, tmp_path: Path) -> None:
        # REQ-FS-003 (validate existence before execution)
        # REQ-FS-004 (deterministic failure if missing)
        missing = str(tmp_path / "does_not_exist.txt")

        result = load_prompt(missing)

        assert isinstance(result, SentinelError)
        assert result.category == FILE_NOT_FOUND
        assert result.location == missing


class TestLoadPromptReadError:
    """Unreadable prompt file returns FILE_READ_ERROR."""

    def test_load_prompt_read_error_is_directory(self, tmp_path: Path) -> None:
        # REQ-FS-004 (deterministic failure when unreadable)
        dir_path = tmp_path / "a_directory"
        dir_path.mkdir()

        result = load_prompt(str(dir_path))

        assert isinstance(result, SentinelError)
        assert result.category == FILE_READ_ERROR
        assert result.location == str(dir_path)


# ---------------------------------------------------------------------------
# load_schema
# ---------------------------------------------------------------------------

class TestLoadSchemaSuccess:
    """Successful schema loading."""

    def test_load_schema_success_dict(self, tmp_path: Path) -> None:
        # REQ-FS-002 (schema from file, JSON)
        # REQ-D-001 (supports schema input – loaded as JSON)
        # REQ-D-004 (read as UTF-8)
        schema_file = tmp_path / "schema.json"
        schema_obj = {"type": "object", "properties": {"name": {"type": "string"}}}
        schema_file.write_text(json.dumps(schema_obj), encoding="utf-8")

        result = load_schema(str(schema_file))

        assert isinstance(result, dict)
        assert result == schema_obj

    def test_load_schema_success_list(self, tmp_path: Path) -> None:
        # REQ-FS-002 (JSON arrays are valid top-level)
        schema_file = tmp_path / "array.json"
        schema_arr = [{"type": "string"}, {"type": "number"}]
        schema_file.write_text(json.dumps(schema_arr), encoding="utf-8")

        result = load_schema(str(schema_file))

        assert isinstance(result, list)
        assert result == schema_arr


class TestLoadSchemaInvalidJson:
    """Invalid JSON returns SCHEMA_INVALID error."""

    def test_load_schema_invalid_json(self, tmp_path: Path) -> None:
        # REQ-D-002 (schema correctness pre-flight: must be valid JSON)
        schema_file = tmp_path / "bad.json"
        schema_file.write_text("{not valid json}", encoding="utf-8")

        result = load_schema(str(schema_file))

        assert isinstance(result, SentinelError)
        assert result.category == SCHEMA_INVALID
        assert result.code == "SENTINEL_SCHEMA_INVALID_JSON"
        assert result.details is not None
        assert result.details["path"] == str(schema_file)
        assert isinstance(result.details["error"], str)
        assert len(result.details["error"]) > 0

    def test_load_schema_empty_file_is_invalid_json(self, tmp_path: Path) -> None:
        # REQ-D-002 (empty file is not valid JSON)
        schema_file = tmp_path / "empty.json"
        schema_file.write_text("", encoding="utf-8")

        result = load_schema(str(schema_file))

        assert isinstance(result, SentinelError)
        assert result.category == SCHEMA_INVALID


class TestLoadSchemaMissing:
    """Missing schema file returns FILE_NOT_FOUND."""

    def test_load_schema_missing_file(self, tmp_path: Path) -> None:
        # REQ-FS-003 (validate existence before execution)
        # REQ-FS-004 (deterministic failure if missing)
        missing = str(tmp_path / "no_schema.json")

        result = load_schema(missing)

        assert isinstance(result, SentinelError)
        assert result.category == FILE_NOT_FOUND
        assert result.location == missing


class TestLoadSchemaReadError:
    """Unreadable schema file returns FILE_READ_ERROR."""

    def test_load_schema_read_error_is_directory(self, tmp_path: Path) -> None:
        # REQ-FS-004 (deterministic failure when unreadable)
        dir_path = tmp_path / "a_directory"
        dir_path.mkdir()

        result = load_schema(str(dir_path))

        assert isinstance(result, SentinelError)
        assert result.category == FILE_READ_ERROR
        assert result.location == str(dir_path)


# ---------------------------------------------------------------------------
# No exceptions leak
# ---------------------------------------------------------------------------

class TestNoExceptionsLeak:
    """Core file loaders must never raise – always return a value."""

    def test_prompt_missing_no_raise(self, tmp_path: Path) -> None:
        result = load_prompt(str(tmp_path / "nope"))
        assert isinstance(result, (str, SentinelError))

    def test_schema_missing_no_raise(self, tmp_path: Path) -> None:
        result = load_schema(str(tmp_path / "nope"))
        assert isinstance(result, (dict, list, SentinelError))

    def test_prompt_directory_no_raise(self, tmp_path: Path) -> None:
        result = load_prompt(str(tmp_path))
        assert isinstance(result, (str, SentinelError))

    def test_schema_directory_no_raise(self, tmp_path: Path) -> None:
        result = load_schema(str(tmp_path))
        assert isinstance(result, (dict, list, SentinelError))
