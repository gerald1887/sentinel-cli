"""Smoke coverage for CLI steps typical of audit pipelines (no bash scripts)."""

from __future__ import annotations

from pathlib import Path

from sentinel.cli import main


def test_audit_pipeline_validate_contract_fixture() -> None:
    root = Path(__file__).resolve().parents[2]
    valid = root / "examples" / "fixtures" / "contract_check" / "validate_input_valid.json"
    schema = root / "examples" / "fixtures" / "contract_check" / "extraction_schema.json"
    assert valid.exists() and schema.exists()
    assert main(["validate", "--input", str(valid), "--schema", str(schema)]) == 0


def test_audit_pipeline_guard_on_contract_fixture(tmp_path) -> None:
    root = Path(__file__).resolve().parents[2]
    valid = root / "examples" / "fixtures" / "contract_check" / "validate_input_valid.json"
    yaml_assert = tmp_path / "assert.yaml"
    yaml_assert.write_text(
        'version: "1"\nassertions:\n  - id: has_age\n    type: exists\n    path: /age\n',
        encoding="utf-8",
    )
    assert main(["guard", "check", "--input", str(valid), "--assertions", str(yaml_assert)]) == 0
