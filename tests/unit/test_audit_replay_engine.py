from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sentinel.audit.builder import build_audit_record_from_result
from sentinel.audit.hashing import _hash_normalized
from sentinel.audit.replay_engine import replay_record
from sentinel.audit.types import AuditConfigs, AuditHashes, AuditInputRefs, AuditRecord
from sentinel.core.runner import RunResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result_file(tmp_path: Path, extra: dict | None = None) -> Path:
    """Write a minimal result artifact to disk and return the path."""
    artifact: dict[str, Any] = {
        "prompt_path": "prompt.json",
        "schema_path": "schema.json",
        "provider": "dummy",
        "model": "dummy-model",
        "timeout": 1,
        "status": "PASS",
    }
    if extra:
        artifact.update(extra)
    p = tmp_path / "result.json"
    p.write_text(json.dumps(artifact), encoding="utf-8")
    return p


def _build_record(tmp_path: Path, extra: dict | None = None) -> AuditRecord:
    result_file = _make_result_file(tmp_path, extra)
    return build_audit_record_from_result(
        command=None,
        execution_id=None,
        result_path=str(result_file),
        prompt_file=None,
        schema_file=None,
        suite_file=None,
        assertions_file=None,
        signals_file=None,
        rules_file=None,
        events_file=None,
    )


def _stub_runner(status: str, approved_output: Any = None):
    """Return a runner callable that always returns the given RunResult."""

    def _runner(*_: object, **__: object) -> RunResult:
        return RunResult(status=status, approved_output=approved_output, error=None)

    return _runner


# ---------------------------------------------------------------------------
# Unpatched round-trip tests (positive and negative)
# ---------------------------------------------------------------------------


def test_replay_roundtrip_pass(tmp_path: Path) -> None:
    """Builder-created record replays PASS when the runner returns an identical artifact."""
    # REQ-AUDIT-REPLAY-01: replay hash comparison covers the full result artifact.
    approved = {"answer": "yes", "score": 42}
    record = _build_record(tmp_path, extra={"approved_output": approved})

    result = replay_record(record, runner=_stub_runner("PASS", approved_output=approved))

    assert result.status == "PASS"
    assert result.audit_id == record.audit_id
    assert result.expected_hash == result.actual_hash


def test_replay_roundtrip_fail_on_different_output(tmp_path: Path) -> None:
    """Builder-created record replays FAIL when approved_output differs."""
    # REQ-AUDIT-REPLAY-02: hash mismatch on differing output is correctly detected.
    original_output = {"answer": "yes"}
    different_output = {"answer": "no"}
    record = _build_record(tmp_path, extra={"approved_output": original_output})

    result = replay_record(record, runner=_stub_runner("PASS", approved_output=different_output))

    assert result.status == "FAIL"
    assert result.actual_hash != result.expected_hash


def test_replay_roundtrip_fail_on_different_status(tmp_path: Path) -> None:
    """Builder-created record replays FAIL when the run status changes."""
    record = _build_record(tmp_path)  # original status=PASS

    result = replay_record(record, runner=_stub_runner("FAIL", approved_output=None))

    assert result.status == "FAIL"


def test_replay_roundtrip_no_approved_output(tmp_path: Path) -> None:
    """Record with no approved_output replays PASS when runner returns no approved_output."""
    record = _build_record(tmp_path)  # no approved_output field

    result = replay_record(record, runner=_stub_runner("PASS", approved_output=None))

    assert result.status == "PASS"
    assert result.expected_hash == result.actual_hash


# ---------------------------------------------------------------------------
# Rewritten tests using public seams (no private-function monkeypatching)
# ---------------------------------------------------------------------------


def test_replay_pass_when_hash_matches(tmp_path: Path) -> None:
    """Replay engine returns PASS when reconstructed artifact matches stored hash."""
    approved = {"value": 1}
    record = _build_record(tmp_path, extra={"approved_output": approved})

    result = replay_record(record, runner=_stub_runner("PASS", approved_output=approved))

    assert result.status == "PASS"


def test_replay_fail_when_hash_mismatch(tmp_path: Path) -> None:
    """Replay engine returns FAIL when reconstructed artifact differs from stored hash."""
    record = _build_record(tmp_path, extra={"approved_output": {"value": 1}})

    result = replay_record(
        record, runner=_stub_runner("PASS", approved_output={"value": 999})
    )

    assert result.status == "FAIL"


# ---------------------------------------------------------------------------
# Edge-case and error-path tests
# ---------------------------------------------------------------------------


def _base_record() -> AuditRecord:
    """Minimal record with a known result_hash for error-path testing."""
    result: dict[str, Any] = {
        "prompt_path": "prompt.json",
        "schema_path": "schema.json",
        "provider": "dummy",
        "model": "dummy-model",
        "timeout": 1,
        "status": "PASS",
    }
    return AuditRecord(
        audit_version="1",
        audit_id="a1",
        timestamp_utc="2024-01-01T00:00:00Z",
        command="audit record",
        execution_id="exec",
        input_refs=AuditInputRefs(
            prompt_file=None,
            schema_file=None,
            suite_file=None,
            assertions_file=None,
            signals_file=None,
            rules_file=None,
        ),
        configs=AuditConfigs(schema=None, assertions=None, signals=None, rules=None),
        result=result,
        event_ids=[],
        hashes=AuditHashes(
            input_hash="i",
            config_hash="c",
            result_hash=_hash_normalized(result),
            full_hash="full",
        ),
        metadata=None,
    )


def test_replay_error_on_missing_required_fields() -> None:
    """Record missing replay fields returns ERROR status."""
    record = AuditRecord(
        audit_version="1",
        audit_id="a2",
        timestamp_utc="2024-01-01T00:00:00Z",
        command="audit record",
        execution_id="exec",
        input_refs=AuditInputRefs(
            prompt_file=None,
            schema_file=None,
            suite_file=None,
            assertions_file=None,
            signals_file=None,
            rules_file=None,
        ),
        configs=AuditConfigs(schema=None, assertions=None, signals=None, rules=None),
        result={"status": "PASS"},  # missing required fields
        event_ids=[],
        hashes=AuditHashes(
            input_hash="i", config_hash="c", result_hash="r", full_hash="f"
        ),
        metadata=None,
    )

    result = replay_record(record, runner=_stub_runner("PASS"))

    assert result.status == "ERROR"
    assert "non-replayable" in result.message


def test_replay_error_propagated_from_runner() -> None:
    """Runner returning ERROR propagates as replay ERROR."""
    from sentinel.core.errors import INTERNAL_ERROR, SentinelError

    record = _base_record()

    def error_runner(*_: object, **__: object) -> RunResult:
        return RunResult(
            status="ERROR",
            error=SentinelError(
                category=INTERNAL_ERROR,
                code="SENTINEL_INTERNAL_ERROR",
                message="provider down",
            ),
            approved_output=None,
        )

    result = replay_record(record, runner=error_runner)

    assert result.status == "ERROR"
