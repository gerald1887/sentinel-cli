from __future__ import annotations

import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Iterator, TextIO

from .types import AuditRecord


class AuditStoreError(Exception):
    pass


def _open_append_only(path: Path) -> TextIO:
    # Open in append+read mode without truncation.
    try:
        return path.open("a+", encoding="utf-8")
    except OSError as exc:
        raise AuditStoreError(f"failed to open audit file for append: {path}") from exc


def append_record(path: str, record: AuditRecord) -> None:
    """Append a single audit record as JSONL without modifying existing contents."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with _open_append_only(file_path) as f:
        f.seek(0, io.SEEK_END)
        try:
            payload = json.dumps(asdict(record), separators=(",", ":"), sort_keys=False)
        except (TypeError, ValueError) as exc:
            raise AuditStoreError("failed to serialize audit record") from exc
        line = payload + "\n"
        try:
            f.write(line)
            f.flush()
        except OSError as exc:
            raise AuditStoreError("failed to write audit record") from exc


def _iter_lines(f: TextIO) -> Iterator[str]:
    for line in f:
        # Preserve exact line boundaries for partial-write detection.
        if not line.endswith("\n"):
            # Treat partial trailing line as ERROR.
            raise AuditStoreError("detected partial audit record write")
        stripped = line.strip()
        if not stripped:
            # Empty lines are invalid in strict JSONL.
            raise AuditStoreError("invalid empty line in audit file")
        yield stripped


def read_records(path: str) -> Iterable[AuditRecord]:
    """Read and validate all audit records from a JSONL audit file."""
    file_path = Path(path)
    if not file_path.exists():
        raise AuditStoreError(f"audit file not found: {path}")

    try:
        with file_path.open("r", encoding="utf-8") as f:
            for raw in _iter_lines(f):
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise AuditStoreError("invalid JSON in audit file") from exc

                if not isinstance(obj, dict):
                    raise AuditStoreError("audit record must be JSON object")

                try:
                    yield _dict_to_audit_record(obj)
                except ValueError as exc:
                    raise AuditStoreError(str(exc)) from exc
    except OSError as exc:
        raise AuditStoreError(f"failed to read audit file: {path}") from exc


def _dict_to_audit_record(data: dict) -> AuditRecord:
    # Strict field validation according to schema specification.
    required_top = {
        "audit_version",
        "audit_id",
        "timestamp_utc",
        "command",
        "execution_id",
        "input_refs",
        "configs",
        "result",
        "event_ids",
        "hashes",
        "metadata",
    }
    missing = required_top.difference(data.keys())
    extra = set(data.keys()).difference(required_top)
    if missing:
        raise ValueError(f"missing required audit fields: {sorted(missing)}")
    if extra:
        raise ValueError(f"unexpected audit fields: {sorted(extra)}")

    from .types import AuditConfigs, AuditHashes, AuditInputRefs  # local import to avoid cycles

    input_refs_obj = data["input_refs"]
    if not isinstance(input_refs_obj, dict):
        raise ValueError("input_refs must be object")
    input_refs = AuditInputRefs(
        prompt_file=input_refs_obj.get("prompt_file"),
        schema_file=input_refs_obj.get("schema_file"),
        suite_file=input_refs_obj.get("suite_file"),
        assertions_file=input_refs_obj.get("assertions_file"),
        signals_file=input_refs_obj.get("signals_file"),
        rules_file=input_refs_obj.get("rules_file"),
    )

    configs_obj = data["configs"]
    if not isinstance(configs_obj, dict):
        raise ValueError("configs must be object")
    configs = AuditConfigs(
        schema=configs_obj.get("schema"),
        assertions=configs_obj.get("assertions"),
        signals=configs_obj.get("signals"),
        rules=configs_obj.get("rules"),
    )

    hashes_obj = data["hashes"]
    if not isinstance(hashes_obj, dict):
        raise ValueError("hashes must be object")
    required_hash_fields = {"input_hash", "config_hash", "result_hash", "full_hash"}
    missing_hash = required_hash_fields.difference(hashes_obj.keys())
    extra_hash = set(hashes_obj.keys()).difference(required_hash_fields)
    if missing_hash:
        raise ValueError(f"missing required hash fields: {sorted(missing_hash)}")
    if extra_hash:
        raise ValueError(f"unexpected hash fields: {sorted(extra_hash)}")
    hashes = AuditHashes(
        input_hash=hashes_obj["input_hash"],
        config_hash=hashes_obj["config_hash"],
        result_hash=hashes_obj["result_hash"],
        full_hash=hashes_obj["full_hash"],
    )

    event_ids = data["event_ids"]
    if not isinstance(event_ids, list) or not all(isinstance(e, str) for e in event_ids):
        raise ValueError("event_ids must be list[str]")

    metadata = data["metadata"]
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be object or null")
        for key, value in metadata.items():
            if not isinstance(key, str):
                raise ValueError("metadata keys must be strings")
            if not (
                value is None
                or isinstance(value, (str, int, float, bool))
            ):
                raise ValueError("metadata values must be flat scalars or null")

    result_obj = data["result"]
    if not isinstance(result_obj, dict):
        raise ValueError("result must be object")

    return AuditRecord(
        audit_version=str(data["audit_version"]),
        audit_id=str(data["audit_id"]),
        timestamp_utc=str(data["timestamp_utc"]),
        command=str(data["command"]),
        execution_id=str(data["execution_id"]),
        input_refs=input_refs,
        configs=configs,
        result=result_obj,
        event_ids=event_ids,
        hashes=hashes,
        metadata=metadata,
    )

