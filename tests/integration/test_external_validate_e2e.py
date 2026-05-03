# This test requires external repository and is skipped in public repo
"""External integration: deterministic extractor replay to Sentinel validate end-to-end."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


def _sentinel_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _external_repo_root() -> Path:
    override = os.environ.get("EXTERNAL_EXTRACTION_REPO")
    if override:
        return Path(override).expanduser().resolve()
    return (_sentinel_root().parent / "external-extraction-example").resolve()


def _pythonpath_with_sentinel() -> str:
    sentinel_root = str(_sentinel_root())
    existing = os.environ.get("PYTHONPATH")
    if existing:
        return f"{sentinel_root}:{existing}"
    return sentinel_root


def _write_local_sentinel_bin(temp_root: Path) -> Path:
    sentinel_bin = temp_root / "sentinel-local.sh"
    sentinel_bin.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "exec python3 -m sentinel.cli \"$@\"\n",
        encoding="utf-8",
    )
    sentinel_bin.chmod(0o755)
    return sentinel_bin


class TestExternalValidateE2E(unittest.TestCase):
    def test_external_replay_to_sentinel_validate(self) -> None:
        ext_root = _external_repo_root()
        if not ext_root.exists():
            self.skipTest("External repository not available; skipping test")

        schema_path = ext_root / "schemas/extraction_schema.json"
        if not schema_path.exists():
            self.skipTest("External repository not available; skipping test")

        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            work_dir = temp_root / "external_run"
            work_dir.mkdir()
            input_path = work_dir / "input.txt"
            replay_path = work_dir / "replay_output.txt"
            extracted_path = work_dir / "result.json"
            unified_artifact_path = work_dir / "validation_success.json"
            sentinel_schema_path = _sentinel_root() / "examples/fixtures/contract_check/artifact_schema.json"

            input_path.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            replay_path.write_text(
                '{"name":"John Doe","age":30,"city":"Bangalore"}',
                encoding="utf-8",
            )
            sentinel_bin = _write_local_sentinel_bin(temp_root)

            env = dict(os.environ)
            env["PYTHONPATH"] = _pythonpath_with_sentinel()

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
            self.assertEqual(extract_proc.returncode, 0, extract_proc.stdout + extract_proc.stderr)
            self.assertTrue(extracted_path.exists())

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
                str(unified_artifact_path),
            ]
            external_validate_proc = subprocess.run(
                external_validate_cmd,
                cwd=str(ext_root),
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                external_validate_proc.returncode,
                0,
                external_validate_proc.stdout + external_validate_proc.stderr,
            )
            self.assertTrue(unified_artifact_path.exists())

            sentinel_validate_cmd = [
                str(sentinel_bin),
                "validate",
                "--input",
                str(unified_artifact_path),
                "--schema",
                str(sentinel_schema_path),
            ]
            sentinel_validate_proc = subprocess.run(
                sentinel_validate_cmd,
                cwd=str(_sentinel_root()),
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                sentinel_validate_proc.returncode,
                0,
                sentinel_validate_proc.stdout + sentinel_validate_proc.stderr,
            )
            self.assertIn("PASS: Contract satisfied", sentinel_validate_proc.stdout)
