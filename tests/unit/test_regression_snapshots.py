"""Unit tests for Regression snapshot path/read/write."""

from __future__ import annotations

from pathlib import Path

from sentinel.core.errors import FILE_NOT_FOUND, SentinelError
from sentinel.testkit.snapshots import (
    SNAPSHOT_INVALID,
    read_snapshot,
    resolve_snapshot_path,
    write_snapshot,
)


def test_resolve_snapshot_path_deterministic() -> None:
    suite_path = "/tmp/my_suite.yaml"
    path = resolve_snapshot_path(suite_path, "user_profile_case")
    assert path == "/tmp/snapshots/user_profile_case.json"


def test_read_existing_valid_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshots" / "case-1.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text('{"ok": true, "value": 1}\n', encoding="utf-8")

    result = read_snapshot(str(snapshot_path))
    assert isinstance(result, dict)
    assert result == {"ok": True, "value": 1}


def test_read_missing_snapshot_returns_deterministic_error(tmp_path: Path) -> None:
    result = read_snapshot(str(tmp_path / "snapshots" / "missing.json"))
    assert isinstance(result, SentinelError)
    assert result.category == FILE_NOT_FOUND


def test_read_invalid_snapshot_json_returns_deterministic_error(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshots" / "bad.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text("{not json}", encoding="utf-8")

    result = read_snapshot(str(snapshot_path))
    assert isinstance(result, SentinelError)
    assert result.category == SNAPSHOT_INVALID
    assert result.code == "SENTINEL_SNAPSHOT_INVALID_JSON"
    assert "valid JSON" in result.message


def test_write_snapshot_creates_directory_and_file(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshots" / "new_case.json"

    error = write_snapshot(str(snapshot_path), {"b": 2, "a": 1})
    assert error is None
    assert snapshot_path.exists()


def test_write_snapshot_overwrites_existing_file(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshots" / "case.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text('{"old": true}\n', encoding="utf-8")

    error = write_snapshot(str(snapshot_path), {"new": True})
    assert error is None

    result = read_snapshot(str(snapshot_path))
    assert isinstance(result, dict)
    assert result == {"new": True}


def test_write_snapshot_json_formatting_is_deterministic(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "snapshots" / "fmt.json"
    payload = {"z": 3, "a": {"y": 2, "x": 1}}

    error = write_snapshot(str(snapshot_path), payload)
    assert error is None

    text = snapshot_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '  "a": {' in text
    assert text.index('"a"') < text.index('"z"')

