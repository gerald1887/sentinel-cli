from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel.audit.builder import AuditBuilderError, build_audit_record_from_result


def _write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj), encoding="utf-8")


def test_builder_loads_result_and_embeds_configs_and_events(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    schema_path = tmp_path / "schema.json"
    assertions_path = tmp_path / "assertions.json"
    events_path = tmp_path / "events.jsonl"

    _write_json(result_path, {"command": "run", "execution_id": "exec-1", "status": "PASS"})
    _write_json(schema_path, {"type": "object"})
    _write_json(assertions_path, {"assertions": []})
    events_path.write_text(  # noqa: E501
        '{"event_version":"1.0","event_id":"e1","event_type":"t","timestamp_utc":"2026-01-01T00:00:00Z","command":"c","provider":null,"model":null,"suite_case_id":null,"status":"PASS","exit_code":0,"duration_ms":1,"contract_status":null,"guard_status":null,"drift_status":null,"error_category":null,"error_code":null,"refusal_detected":null,"input_tokens":null,"output_tokens":null,"total_tokens":null,"artifact_refs":{"source":"s"},"metadata":null}\n',
        encoding="utf-8",
    )

    record = build_audit_record_from_result(
        command="audit record",
        execution_id="exec-1",
        result_path=str(result_path),
        prompt_file=None,
        schema_file=str(schema_path),
        suite_file=None,
        assertions_file=str(assertions_path),
        signals_file=None,
        rules_file=None,
        events_file=str(events_path),
    )

    assert record.result["status"] == "PASS"
    assert record.command == "run"
    assert record.execution_id == "exec-1"
    assert record.configs.schema == {"type": "object"}
    assert record.configs.assertions == {"assertions": []}
    assert record.event_ids == ["e1"]
    assert record.hashes.input_hash
    assert record.hashes.config_hash
    assert record.hashes.result_hash
    assert record.hashes.full_hash


def test_builder_errors_on_missing_result(tmp_path: Path) -> None:
    with pytest.raises(AuditBuilderError):
        build_audit_record_from_result(
            command="audit record",
            execution_id="exec-1",
            result_path=str(tmp_path / "missing.json"),
            prompt_file=None,
            schema_file=None,
            suite_file=None,
            assertions_file=None,
            signals_file=None,
            rules_file=None,
            events_file=None,
        )

