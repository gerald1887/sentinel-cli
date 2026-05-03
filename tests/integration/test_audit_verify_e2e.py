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


def test_verify_pass_exit_zero(tmp_path: Path, capsys) -> None:
    audit_file = tmp_path / "audit.jsonl"
    result_path = _write_result(tmp_path, "PASS")

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

    exit_code = main(
        [
            "audit",
            "verify",
            "--audit-file",
            str(audit_file),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "AUDIT VERIFY SUMMARY total_records=1 valid=1 invalid=0" in captured.out


def test_verify_fail_exit_two_on_tamper(tmp_path: Path, capsys) -> None:
    audit_file = tmp_path / "audit.jsonl"
    result_path = _write_result(tmp_path, "PASS")

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

    # Tamper stored record's result content to violate hash.
    text = audit_file.read_text(encoding="utf-8")
    obj = json.loads(text.splitlines()[0])
    obj["result"]["status"] = "TAMPERED"
    audit_file.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    exit_code = main(
        [
            "audit",
            "verify",
            "--audit-file",
            str(audit_file),
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "AUDIT VERIFY SUMMARY total_records=1 valid=0 invalid=1" in captured.out
    # Only FAIL lines are printed after the summary.
    assert "AUDIT FAIL " in captured.out
    assert "AUDIT ERROR " not in captured.out

