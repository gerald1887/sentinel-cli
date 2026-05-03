# This test requires external repository and is skipped in public repo
"""External integration: Sentinel validate as an external reliability gate."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestExternalValidateReliabilityGate(unittest.TestCase):
    def test_success_path_external_system_artifact_passes(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        ext_repo = os.environ.get("EXTERNAL_EXTRACTION_REPO")
        ext_root = (
            Path(ext_repo).expanduser().resolve()
            if ext_repo
            else (sentinel_root.parent / "external-extraction-example").resolve()
        )
        if not ext_root.exists():
            self.skipTest("External repository not available; skipping test")

        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            input_path = temp_root / "input.txt"
            replay_path = temp_root / "replay_output.txt"
            extracted_path = temp_root / "result.json"
            sentinel_wrapper = temp_root / "sentinel-local.sh"
            valid_artifact = temp_root / "validation_success.json"

            input_path.write_text("John Doe is 30 years old and lives in Bangalore.", encoding="utf-8")
            replay_path.write_text('{"name":"John Doe","age":30,"city":"Bangalore"}', encoding="utf-8")
            sentinel_wrapper.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                "exec python3 -m sentinel.cli \"$@\"\n",
                encoding="utf-8",
            )
            sentinel_wrapper.chmod(0o755)

            extract_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "extractor.cli",
                    "run",
                    "--input",
                    str(input_path),
                    "--schema",
                    str(ext_root / "schemas/extraction_schema.json"),
                    "--output",
                    str(extracted_path),
                    "--replay-output",
                    str(replay_path),
                ],
                cwd=str(ext_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(extract_proc.returncode, 0, extract_proc.stdout + extract_proc.stderr)

            produce_artifact_proc = subprocess.run(
                [
                    "python3",
                    "scripts/validate_artifact_sentinel.py",
                    "--input",
                    str(extracted_path),
                    "--schema",
                    str(ext_root / "schemas/extraction_schema.json"),
                    "--sentinel-bin",
                    str(sentinel_wrapper),
                    "--success-output",
                    str(valid_artifact),
                ],
                cwd=str(ext_root),
                env={**os.environ, "PYTHONPATH": str(sentinel_root)},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                produce_artifact_proc.returncode,
                0,
                produce_artifact_proc.stdout + produce_artifact_proc.stderr,
            )

            validate_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "validate",
                    "--input",
                    str(valid_artifact),
                    "--schema",
                    "examples/fixtures/contract_check/artifact_schema.json",
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validate_proc.returncode, 0, validate_proc.stdout + validate_proc.stderr)
            self.assertIn("PASS: Contract satisfied", validate_proc.stdout)

    def test_failure_path_invalid_artifact_fails(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        invalid_artifact = sentinel_root / "examples/fixtures/contract_check/artifact_invalid.json"

        validate_proc = subprocess.run(
            [
                "python3",
                "-m",
                "sentinel.cli",
                "validate",
                "--input",
                str(invalid_artifact),
                "--schema",
                "examples/fixtures/contract_check/artifact_schema.json",
            ],
            cwd=str(sentinel_root),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(validate_proc.returncode, 1, validate_proc.stdout + validate_proc.stderr)
        self.assertIn("FAIL: Contract violated", validate_proc.stdout)
