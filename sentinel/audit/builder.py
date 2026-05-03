from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentinel.core.errors import SentinelError
from sentinel.monitor.event_store import read_events

from .hashing import compute_hashes_for_record_components
from .types import AuditConfigs, AuditInputRefs, AuditRecord


class AuditBuilderError(Exception):
    pass


def _load_json_file(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except FileNotFoundError as exc:
        raise AuditBuilderError(f"missing referenced config file: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditBuilderError(f"invalid JSON config file: {path}") from exc


def _load_result_artifact(path: str) -> Dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
        obj = json.loads(text)
    except FileNotFoundError as exc:
        raise AuditBuilderError(f"missing result artifact: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditBuilderError(f"invalid result artifact: {path}") from exc
    if not isinstance(obj, dict):
        raise AuditBuilderError("result artifact must be JSON object")
    return obj


def _load_event_ids(events_path: Optional[str]) -> List[str]:
    if events_path is None:
        return []
    events = read_events(events_path)
    if isinstance(events, SentinelError):
        raise AuditBuilderError("failed to load events file")
    # Preserve file-order lineage.
    event_ids: List[str] = [event.event_id for event in events]
    if not event_ids:
        # Explicit events argument but no linkage is an error.
        raise AuditBuilderError("no events found in provided events file")
    return event_ids


def build_audit_record_from_result(
    *,
    command: str | None,
    execution_id: str | None,
    result_path: str,
    prompt_file: Optional[str],
    schema_file: Optional[str],
    suite_file: Optional[str],
    assertions_file: Optional[str],
    signals_file: Optional[str],
    rules_file: Optional[str],
    events_file: Optional[str],
) -> AuditRecord:
    result_obj = _load_result_artifact(result_path)
    source_command = result_obj.get("command")
    source_execution_id = result_obj.get("execution_id")

    resolved_command = (
        source_command
        if isinstance(source_command, str) and source_command
        else command if command not in (None, "") else "unknown"
    )
    resolved_execution_id = (
        source_execution_id
        if isinstance(source_execution_id, str)
        else execution_id if execution_id not in (None, "") else ""
    )

    input_refs = AuditInputRefs(
        prompt_file=prompt_file,
        schema_file=schema_file,
        suite_file=suite_file,
        assertions_file=assertions_file,
        signals_file=signals_file,
        rules_file=rules_file,
    )

    configs = AuditConfigs(
        schema=_load_json_file(schema_file),
        assertions=_load_json_file(assertions_file),
        signals=_load_json_file(signals_file),
        rules=_load_json_file(rules_file),
    )

    event_ids = _load_event_ids(events_file)

    base_record: Dict[str, Any] = {
        "audit_version": "1",
        "audit_id": str(uuid.uuid4()),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "command": resolved_command,
        "execution_id": resolved_execution_id,
        "input_refs": {
            "prompt_file": input_refs.prompt_file,
            "schema_file": input_refs.schema_file,
            "suite_file": input_refs.suite_file,
            "assertions_file": input_refs.assertions_file,
            "signals_file": input_refs.signals_file,
            "rules_file": input_refs.rules_file,
        },
        "configs": {
            "schema": configs.schema,
            "assertions": configs.assertions,
            "signals": configs.signals,
            "rules": configs.rules,
        },
        "result": result_obj,
        "event_ids": event_ids,
        "hashes": {},  # filled after hashing
        "metadata": None,
    }

    hashes = compute_hashes_for_record_components(
        base_record["input_refs"],
        base_record["configs"],
        base_record["result"],
        {
            **base_record,
            "hashes": {
                "input_hash": "",
                "config_hash": "",
                "result_hash": "",
            },
        },
    )

    base_record["hashes"] = {
        "input_hash": hashes.input_hash,
        "config_hash": hashes.config_hash,
        "result_hash": hashes.result_hash,
        "full_hash": hashes.full_hash,
    }

    return AuditRecord(
        audit_version=base_record["audit_version"],
        audit_id=base_record["audit_id"],
        timestamp_utc=base_record["timestamp_utc"],
        command=base_record["command"],
        execution_id=base_record["execution_id"],
        input_refs=input_refs,
        configs=configs,
        result=result_obj,
        event_ids=event_ids,
        hashes=hashes,
        metadata=None,
    )

