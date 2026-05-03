"""External guardrail gate via sentinel guard check CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestExternalGuardrailGate(unittest.TestCase):
    def test_guard_pass(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            artifact_path = temp_root / "artifact.json"
            assertions_path = temp_root / "assertions.json"

            artifact_path.write_text(
                json.dumps(
                    {
                        "status": "PASS",
                        "exit_code": 0,
                        "stdout": "deterministic output",
                        "stderr": "",
                    }
                ),
                encoding="utf-8",
            )
            assertions_path.write_text(
                json.dumps(
                    {
                        "assertions": [
                            {"id": "a_status", "type": "equals", "path": "/status", "value": "PASS"},
                            {"id": "a_exit", "type": "equals", "path": "/exit_code", "value": 0},
                            {"id": "a_stdout", "type": "exists", "path": "/stdout"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "guard",
                    "check",
                    "--input",
                    str(artifact_path),
                    "--assertions",
                    str(assertions_path),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("GUARD SUMMARY", proc.stdout)
            self.assertIn("fail=0", proc.stdout)
            self.assertIn("error=0", proc.stdout)

    def test_guard_fail(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            artifact_path = temp_root / "artifact.json"
            assertions_path = temp_root / "assertions.json"

            artifact_path.write_text(
                json.dumps(
                    {
                        "status": "FAIL",
                        "exit_code": 1,
                        "stdout": "deterministic output",
                        "stderr": "",
                    }
                ),
                encoding="utf-8",
            )
            assertions_path.write_text(
                json.dumps(
                    {
                        "assertions": [
                            {"id": "a_status", "type": "equals", "path": "/status", "value": "PASS"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "guard",
                    "check",
                    "--input",
                    str(artifact_path),
                    "--assertions",
                    str(assertions_path),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("GUARD SUMMARY", proc.stdout)
            self.assertIn("fail=1", proc.stdout)
            self.assertIn("ASSERT a_status FAIL", proc.stdout)
