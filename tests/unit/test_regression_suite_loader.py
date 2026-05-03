"""Unit tests for Regression suite loader and validation."""

from __future__ import annotations

from pathlib import Path

from sentinel.core.errors import FILE_NOT_FOUND, SCHEMA_INVALID, SentinelError
from sentinel.testkit.suite_loader import load_suite
from sentinel.testkit.types import SuiteCaseDefinition, SuiteDefinition


def _write_suite(tmp_path: Path, content: str, name: str = "suite.yaml") -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_load_suite_valid_minimal_success(tmp_path: Path) -> None:
    suite_path = _write_suite(
        tmp_path,
        """
command: run
cases:
  - id: case-1
    prompt: prompt.txt
    schema: schema.json
    provider: openai
    model: gpt-4.1
""",
    )

    result = load_suite(suite_path)
    assert isinstance(result, SuiteDefinition)
    assert result.command == "run"
    assert result.suite_path == suite_path
    assert len(result.cases) == 1
    assert isinstance(result.cases[0], SuiteCaseDefinition)
    assert result.cases[0].case_id == "case-1"
    assert result.cases[0].contract_version == "v1"
    assert result.cases[0].ignore_paths == ()


def test_load_suite_contract_version_explicit_preserved(tmp_path: Path) -> None:
    suite_path = _write_suite(
        tmp_path,
        """
command: run
cases:
  - id: case-1
    prompt: prompt.txt
    schema: schema.json
    provider: openai
    model: gpt-4.1
    contract_version: v2
""",
    )
    result = load_suite(suite_path)
    assert isinstance(result, SuiteDefinition)
    assert result.cases[0].contract_version == "v2"


def test_load_suite_ignore_paths_loaded_as_tuple_of_strings(tmp_path: Path) -> None:
    suite_path = _write_suite(
        tmp_path,
        """
command: run
cases:
  - id: case-1
    prompt: prompt.txt
    schema: schema.json
    provider: openai
    model: gpt-4.1
    ignore_paths:
      - /meta
      - /ts
""",
    )
    result = load_suite(suite_path)
    assert isinstance(result, SuiteDefinition)
    assert result.cases[0].ignore_paths == ("/meta", "/ts")


def test_load_suite_missing_file_fails_deterministically(tmp_path: Path) -> None:
    result = load_suite(str(tmp_path / "missing.yaml"))
    assert isinstance(result, SentinelError)
    assert result.category == FILE_NOT_FOUND


def test_load_suite_invalid_yaml_fails_deterministically(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, "command: [\ncases: [")
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.category == SCHEMA_INVALID
    assert result.code == "SENTINEL_SUITE_INVALID_YAML"


def test_load_suite_wrong_top_level_type_fails(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, "- not-a-mapping")
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.category == SCHEMA_INVALID
    assert result.code == "SENTINEL_SUITE_INVALID_TOP_LEVEL"


def test_load_suite_missing_cases_fails(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, "command: run")
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_SUITE_MISSING_CASES"


def test_load_suite_empty_cases_fails(tmp_path: Path) -> None:
    suite_path = _write_suite(tmp_path, "command: run\ncases: []")
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_SUITE_EMPTY_CASES"


def test_load_suite_case_missing_id_fails(tmp_path: Path) -> None:
    suite_path = _write_suite(
        tmp_path,
        """
command: run
cases:
  - prompt: prompt.txt
    schema: schema.json
    provider: openai
    model: gpt-4.1
""",
    )
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_SUITE_MISSING_CASE_ID"


def test_load_suite_duplicate_case_ids_fail(tmp_path: Path) -> None:
    suite_path = _write_suite(
        tmp_path,
        """
command: run
cases:
  - id: dup
    prompt: p1.txt
    schema: s1.json
    provider: openai
    model: gpt-4.1
  - id: dup
    prompt: p2.txt
    schema: s2.json
    provider: openai
    model: gpt-4.1
""",
    )
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_SUITE_DUPLICATE_CASE_ID"


def test_load_suite_case_field_type_mismatch_fails(tmp_path: Path) -> None:
    suite_path = _write_suite(
        tmp_path,
        """
command: run
cases:
  - id: case-1
    prompt: prompt.txt
    schema: schema.json
    provider: openai
    model: 123
""",
    )
    result = load_suite(suite_path)
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_SUITE_INVALID_CASE_FIELD_TYPE"

