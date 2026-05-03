from __future__ import annotations

from typing import Any

from sentinel.audit.replay_engine import replay_record
from sentinel.audit.types import AuditConfigs, AuditHashes, AuditInputRefs, AuditRecord
from sentinel.core.runner import RunResult


def _base_record() -> AuditRecord:
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
        result={
            "prompt_path": "prompt.json",
            "schema_path": "schema.json",
            "provider": "dummy",
            "model": "dummy-model",
            "timeout": 1,
            "status": "PASS",
        },
        event_ids=[],
        hashes=AuditHashes(
            input_hash="i",
            config_hash="c",
            result_hash="expected-hash",
            full_hash="full",
        ),
        metadata=None,
    )


def _runner_with_output(output: Any) -> RunResult:
    return RunResult(status="PASS", approved_output=output, error=None)


def test_replay_pass_when_hash_matches() -> None:
    record = _base_record()

    def fake_runner(*_: object, **__: object) -> RunResult:
        # Replay produces content whose hash representation we treat as "expected-hash".
        # The replay_engine uses _hash_normalized over approved_output, so we simulate that
        # by returning sentinel string that we also store in record.hashes.result_hash.
        return _runner_with_output("expected-output")

    # Patch internal hash function to return the precomputed value.
    from sentinel.audit import replay_engine as re_mod  # type: ignore

    def fake_hash_normalized(value: object) -> str:  # noqa: ARG001
        return record.hashes.result_hash

    original = re_mod._hash_normalized
    re_mod._hash_normalized = fake_hash_normalized  # type: ignore[assignment]
    try:
        result = replay_record(record, runner=fake_runner)
    finally:
        re_mod._hash_normalized = original  # type: ignore[assignment]

    assert result.status == "PASS"


def test_replay_fail_when_hash_mismatch() -> None:
    record = _base_record()

    def fake_runner(*_: object, **__: object) -> RunResult:
        return _runner_with_output("different-output")

    from sentinel.audit import replay_engine as re_mod  # type: ignore

    def fake_hash_normalized(value: object) -> str:  # noqa: ARG001
        return "actual-hash"

    original = re_mod._hash_normalized
    re_mod._hash_normalized = fake_hash_normalized  # type: ignore[assignment]
    try:
        result = replay_record(record, runner=fake_runner)
    finally:
        re_mod._hash_normalized = original  # type: ignore[assignment]

    assert result.status == "FAIL"

