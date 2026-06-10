from __future__ import annotations

from typing import Callable

from sentinel.core.errors import INTERNAL_ERROR, SentinelError
from sentinel.core.runner import RunResult, run_contract

from .hashing import HashingError, _hash_normalized  # type: ignore[attr-defined]
from .types import AuditRecord, AuditReplayResult


class ReplayError(Exception):
    pass


def _run_core_contract(
    prompt_path: str,
    schema_path: str,
    provider: str,
    model: str,
    timeout: int,
) -> RunResult:
    return run_contract(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider=provider,
        model=model,
        timeout=timeout,
    )


def replay_record(
    record: AuditRecord,
    *,
    runner: Callable[[str, str, str, str, int], RunResult] = _run_core_contract,
) -> AuditReplayResult:
    """Replay a single audit record deterministically.

    Replay is only supported for contract run results where the stored result contains the
    fields required to call ``run_contract`` again.
    """
    # Determine replayability based on stored content.
    result = record.result
    required_fields = ["prompt_path", "schema_path", "provider", "model", "timeout"]
    missing = [field for field in required_fields if field not in result]
    if missing:
        return AuditReplayResult(
            audit_id=record.audit_id,
            status="ERROR",
            expected_hash=record.hashes.result_hash,
            actual_hash=None,
            message=f"non-replayable record, missing fields: {', '.join(missing)}",
        )

    prompt_path = str(result["prompt_path"])
    schema_path = str(result["schema_path"])
    provider = str(result["provider"])
    model = str(result["model"])
    timeout = int(result["timeout"])

    run = runner(
        prompt_path=prompt_path,
        schema_path=schema_path,
        provider=provider,
        model=model,
        timeout=timeout,
    )

    if run.status == "ERROR":
        err: SentinelError | None = run.error
        message = "replay evaluator error"
        if err is not None:
            message = f"{err.category} {err.code} {err.message}"
        return AuditReplayResult(
            audit_id=record.audit_id,
            status="ERROR",
            expected_hash=record.hashes.result_hash,
            actual_hash=None,
            message=message,
        )

    if run.status not in ("PASS", "FAIL"):
        return AuditReplayResult(
            audit_id=record.audit_id,
            status="ERROR",
            expected_hash=record.hashes.result_hash,
            actual_hash=None,
            message="unsupported replay status",
        )

    # Reconstruct the full result artifact the same way the builder does: hash the
    # complete result dict, not just approved_output. Start from the stored result
    # (which has all the original fields) and replace the mutable output fields.
    replay_artifact: dict = {**record.result}
    replay_artifact["status"] = run.status
    if run.approved_output is not None:
        replay_artifact["approved_output"] = run.approved_output
    elif "approved_output" in replay_artifact:
        del replay_artifact["approved_output"]

    try:
        actual_hash = _hash_normalized(replay_artifact)
    except HashingError as exc:
        return AuditReplayResult(
            audit_id=record.audit_id,
            status="ERROR",
            expected_hash=record.hashes.result_hash,
            actual_hash=None,
            message=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        return AuditReplayResult(
            audit_id=record.audit_id,
            status="ERROR",
            expected_hash=record.hashes.result_hash,
            actual_hash=None,
            message=f"{INTERNAL_ERROR} replay hashing failed: {exc}",
        )

    expected_hash = record.hashes.result_hash
    if actual_hash == expected_hash:
        return AuditReplayResult(
            audit_id=record.audit_id,
            status="PASS",
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            message="replay match",
        )

    return AuditReplayResult(
        audit_id=record.audit_id,
        status="FAIL",
        expected_hash=expected_hash,
        actual_hash=actual_hash,
        message="replay mismatch",
    )

