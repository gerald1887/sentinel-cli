from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main


def _write_result(tmp_path: Path) -> Path:
    result = {
        "command": "run",
        "execution_id": "exec-integration-1",
        "prompt_path": "tests/fixtures/prompt.txt",
        "schema_path": "tests/fixtures/schema.json",
        "provider": "dummy",
        "model": "dummy-model",
        "timeout": 1,
        "status": "PASS",
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def test_audit_record_and_inspect_roundtrip(tmp_path: Path, monkeypatch) -> None:
    audit_file = tmp_path / "audit.jsonl"
    result_path = _write_result(tmp_path)

    exit_code = main(
        [
            "audit",
            "record",
            "--audit-file",
            str(audit_file),
            "--source",
            str(result_path),
        ]
    )
    assert exit_code == 0

    record = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[-1])
    assert record["command"] == "run"
    assert record["execution_id"] == "exec-integration-1"

    exit_code = main(
        [
            "audit",
            "inspect",
            "--audit-file",
            str(audit_file),
        ]
    )
    assert exit_code == 0

