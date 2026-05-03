"""Reliability gates demo: validate + guard outcomes without shell scripts."""

from __future__ import annotations

from pathlib import Path

import pytest

from sentinel.cli import main


@pytest.fixture()
def fx_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "fixtures" / "contract_check"


def test_reliability_demo_validate_and_guard_paths(fx_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    valid = fx_root / "artifact_valid.json"
    invalid = fx_root / "artifact_invalid.json"
    schema = fx_root / "artifact_schema.json"
    assert valid.exists() and invalid.exists() and schema.exists()

    pass_yaml = tmp_path / "guard_pass.yaml"
    pass_yaml.write_text(
        'version: "1"\nassertions:\n  - id: status_pass\n    type: equals\n    path: /status\n    value: PASS\n',
        encoding="utf-8",
    )
    fail_yaml = tmp_path / "guard_fail.yaml"
    fail_yaml.write_text(
        'version: "1"\nassertions:\n  - id: status_is_fail\n    type: equals\n    path: /status\n    value: FAIL\n',
        encoding="utf-8",
    )

    assert main(["validate", "--input", str(valid), "--schema", str(schema)]) == 0
    assert "PASS: Contract satisfied" in capsys.readouterr().out

    assert main(["validate", "--input", str(invalid), "--schema", str(schema)]) == 1
    out_fail = capsys.readouterr().out
    assert "FAIL: Contract violated" in out_fail
    assert "SCHEMA_VALIDATION_ERROR" in out_fail

    assert main(["guard", "check", "--input", str(valid), "--assertions", str(pass_yaml)]) == 0
    assert "GUARD SUMMARY total=1 pass=1 fail=0 error=0" in capsys.readouterr().out

    assert main(["guard", "check", "--input", str(valid), "--assertions", str(fail_yaml)]) == 1
    out_guard = capsys.readouterr().out
    assert "GUARD SUMMARY total=1 pass=0 fail=1 error=0" in out_guard
    assert "ASSERT status_is_fail FAIL" in out_guard


def test_reliability_demo_output_is_deterministic_across_runs(fx_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    valid = fx_root / "artifact_valid.json"
    schema = fx_root / "artifact_schema.json"
    pass_yaml = tmp_path / "guard_pass.yaml"
    pass_yaml.write_text(
        'version: "1"\nassertions:\n  - id: status_pass\n    type: equals\n    path: /status\n    value: PASS\n',
        encoding="utf-8",
    )

    def run_once() -> str:
        main(["validate", "--input", str(valid), "--schema", str(schema)])
        capsys.readouterr()
        main(["guard", "check", "--input", str(valid), "--assertions", str(pass_yaml)])
        return capsys.readouterr().out

    assert run_once() == run_once()
