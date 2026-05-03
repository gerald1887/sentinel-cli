from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main


def _write_result(tmp_path: Path, status: str, provider: str, model: str) -> Path:
    result = {
        "prompt_path": "prompt.json",
        "schema_path": "schema.json",
        "provider": provider,
        "model": model,
        "timeout": 1,
        "status": status,
    }
    path = tmp_path / f"result_{status}_{provider}_{model}.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def test_inspect_filters_and_last(tmp_path: Path, capsys) -> None:
    audit_file = tmp_path / "audit.jsonl"

    r1 = _write_result(tmp_path, "PASS", "p1", "m1")
    r2 = _write_result(tmp_path, "FAIL", "p2", "m2")

    assert (
        main(["audit", "record", "--audit-file", str(audit_file), "--source", str(r1)]) == 0
    )
    assert (
        main(["audit", "record", "--audit-file", str(audit_file), "--source", str(r2)]) == 0
    )

    exit_code = main(
        [
            "audit",
            "inspect",
            "--audit-file",
            str(audit_file),
            "--provider",
            "p2",
            "--last",
            "1",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["result"]["provider"] == "p2"
    assert row["result"]["model"] == "m2"

