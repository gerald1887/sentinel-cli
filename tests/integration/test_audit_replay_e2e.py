from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main


def _write_result(tmp_path: Path, status: str) -> Path:
    result = {
        "prompt_path": "prompt.json",
        "schema_path": "schema.json",
        "provider": "dummy",
        "model": "dummy-model",
        "timeout": 1,
        "status": status,
    }
    path = tmp_path / f"result_{status}.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def _record_and_get_audit_id(audit_file: Path, result_path: Path) -> str:
    assert (
        main(
            [
                "audit",
                "record",
                "--audit-file",
                str(audit_file),
                "--source",
                str(result_path),
            ]
        )
        == 0
    )
    # Read last line and return audit_id.
    last_line = audit_file.read_text(encoding="utf-8").splitlines()[-1]
    obj = json.loads(last_line)
    return obj["audit_id"]


def test_replay_error_exit_two_for_missing_files(tmp_path: Path, capsys) -> None:
    audit_file = tmp_path / "audit.jsonl"
    result_path = _write_result(tmp_path, "PASS")
    audit_id = _record_and_get_audit_id(audit_file, result_path)

    exit_code = main(
        [
            "audit",
            "replay",
            "--audit-file",
            str(audit_file),
            "--audit-id",
            audit_id,
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "AUDIT REPLAY SUMMARY total=1 pass=0 fail=0 error=1" in captured.out
    assert f"AUDIT ERROR {audit_id} " in captured.out

