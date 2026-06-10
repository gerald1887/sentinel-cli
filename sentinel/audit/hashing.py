from __future__ import annotations

import hashlib
from typing import Any

from .normalizer import NormalizationError, normalize_for_hash
from .types import AuditHashes, AuditRecord


class HashingError(Exception):
    pass


def _hash_normalized(value: Any) -> str:
    try:
        payload = normalize_for_hash(value)
    except NormalizationError as exc:
        raise HashingError("normalization failed for hashing") from exc
    h = hashlib.sha256()
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


def compute_hashes_for_record_components(
    input_refs: Any, configs: Any, result: Any, full_record_without_hashes: dict[str, Any]
) -> AuditHashes:
    """Compute component hashes and full_hash over full record content.

    full_hash is computed over the full audit record where the ``hashes`` object contains
    ``input_hash``, ``config_hash``, and ``result_hash`` but does **not** include
    ``full_hash`` itself, per Audit design.
    """
    input_hash = _hash_normalized(input_refs)
    config_hash = _hash_normalized(configs)
    result_hash = _hash_normalized(result)

    record_copy = dict(full_record_without_hashes)
    record_copy["hashes"] = {
        "input_hash": input_hash,
        "config_hash": config_hash,
        "result_hash": result_hash,
    }
    full_hash = _hash_normalized(record_copy)

    return AuditHashes(
        input_hash=input_hash,
        config_hash=config_hash,
        result_hash=result_hash,
        full_hash=full_hash,
    )


def recompute_hashes_for_record(record: AuditRecord) -> AuditHashes:
    base: dict[str, Any] = {
        "audit_version": record.audit_version,
        "audit_id": record.audit_id,
        "timestamp_utc": record.timestamp_utc,
        "command": record.command,
        "execution_id": record.execution_id,
        "input_refs": {
            "prompt_file": record.input_refs.prompt_file,
            "schema_file": record.input_refs.schema_file,
            "suite_file": record.input_refs.suite_file,
            "assertions_file": record.input_refs.assertions_file,
            "signals_file": record.input_refs.signals_file,
            "rules_file": record.input_refs.rules_file,
        },
        "configs": {
            "schema": record.configs.schema,
            "assertions": record.configs.assertions,
            "signals": record.configs.signals,
            "rules": record.configs.rules,
        },
        "result": record.result,
        "event_ids": list(record.event_ids),
        "hashes": {
            "input_hash": record.hashes.input_hash,
            "config_hash": record.hashes.config_hash,
            "result_hash": record.hashes.result_hash,
            # full_hash excluded from normalization per schema specification.
        },
        "metadata": record.metadata,
    }
    return compute_hashes_for_record_components(
        base["input_refs"],
        base["configs"],
        base["result"],
        base,
    )

