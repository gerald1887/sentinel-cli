# This test requires external repository and is skipped in public repo
"""External integration: invalid unified artifact failure path via CLI subprocesses."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


def _sentinel_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_external_repo() -> Path | None:
    override = os.environ.get("EXTERNAL_EXTRACTION_REPO")
    if override:
        candidate = Path(override).expanduser().resolve()
        if candidate.exists():
            return candidate
        return None

    sibling = (_sentinel_root().parent / "external-extraction-example").resolve()
    if sibling.exists():
        return sibling
    return None


def test_external_invalid_unified_artifact_fails_sentinel_validate() -> None:
    ext_root = _resolve_external_repo()
    if ext_root is None:
        pytest.skip("External repository not available; skipping test")

    schema_path = ext_root / "schemas/extraction_schema.json"
    if not schema_path.exists():
        pytest.skip("External repository not available; skipping test")

    sentinel_unified_schema = _sentinel_root() / "examples/fixtures/contract_check/artifact_schema.json"
    if not sentinel_unified_schema.exists():
        pytest.skip("External repository not available; skipping test")

    with tempfile.TemporaryDirectory() as td:
        temp_root = Path(td)
        input_path = temp_root / "input.txt"
        replay_path = temp_root / "replay_output.txt"
        extracted_path = temp_root / "result.json"
        validation_success = temp_root / "validation_success.json"
        invalid_unified_artifact = temp_root / "validation_success_invalid.json"
        sentinel_bin = temp_root / "sentinel"

        input_path.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
        replay_path.write_text('{"name":"John Doe","age":30,"city":"Bangalore"}', encoding="utf-8")
        sentinel_bin.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "exec python3 -m sentinel.cli \"$@\"\n",
            encoding="utf-8",
        )
        sentinel_bin.chmod(0o755)

        env = dict(os.environ)
        env["PYTHONPATH"] = f"{_sentinel_root()}:{env.get('PYTHONPATH', '')}".rstrip(":")

        extract_cmd = [
            "python3",
            "-m",
            "extractor.cli",
            "run",
            "--input",
            str(input_path),
            "--schema",
            str(schema_path),
            "--output",
            str(extracted_path),
            "--replay-output",
            str(replay_path),
        ]
        extract_proc = subprocess.run(
            extract_cmd,
            cwd=str(ext_root),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert extract_proc.returncode == 0, extract_proc.stdout + extract_proc.stderr

        external_validate_cmd = [
            "python3",
            "scripts/validate_artifact_sentinel.py",
            "--input",
            str(extracted_path),
            "--schema",
            str(schema_path),
            "--sentinel-bin",
            str(sentinel_bin),
            "--success-output",
            str(validation_success),
        ]
        external_validate_proc = subprocess.run(
            external_validate_cmd,
            cwd=str(ext_root),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert external_validate_proc.returncode == 0, external_validate_proc.stdout + external_validate_proc.stderr
        assert validation_success.exists()

        payload = json.loads(validation_success.read_text(encoding="utf-8"))
        payload["status"] = "OK"
        invalid_unified_artifact.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        sentinel_validate_cmd = [
            "sentinel",
            "validate",
            "--input",
            str(invalid_unified_artifact),
            "--schema",
            str(sentinel_unified_schema),
        ]
        sentinel_validate_proc = subprocess.run(
            sentinel_validate_cmd,
            cwd=str(_sentinel_root()),
            env={**env, "PATH": f"{temp_root}:{env.get('PATH', '')}"},
            check=False,
            capture_output=True,
            text=True,
        )
        combined = f"{sentinel_validate_proc.stdout}\n{sentinel_validate_proc.stderr}"
        assert sentinel_validate_proc.returncode == 1, combined
        assert "FAIL: Contract violated" in combined
