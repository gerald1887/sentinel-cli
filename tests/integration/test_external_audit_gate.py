"""External audit integrity gate via audit record/verify CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestExternalAuditGate(unittest.TestCase):
    def test_audit_verify_pass(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            source_path = temp_root / "source.json"
            audit_file = temp_root / "audit.jsonl"

            source_path.write_text(
                json.dumps(
                    {
                        "command": "external.run",
                        "execution_id": "exec-integration-pass",
                        "prompt_path": "prompt.txt",
                        "schema_path": "schema.json",
                        "provider": "dummy",
                        "model": "dummy-model",
                        "timeout": 1,
                        "status": "PASS",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            record_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "audit",
                    "record",
                    "--audit-file",
                    str(audit_file),
                    "--source",
                    str(source_path),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(record_proc.returncode, 0, record_proc.stdout + record_proc.stderr)

            verify_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "audit",
                    "verify",
                    "--audit-file",
                    str(audit_file),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verify_proc.returncode, 0, verify_proc.stdout + verify_proc.stderr)
            self.assertIn("AUDIT VERIFY SUMMARY", verify_proc.stdout)
            self.assertIn("invalid=0", verify_proc.stdout)

    def test_audit_verify_detects_tampering(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            source_path = temp_root / "source.json"
            audit_file = temp_root / "audit.jsonl"

            source_path.write_text(
                json.dumps(
                    {
                        "command": "external.run",
                        "execution_id": "exec-integration-fail",
                        "prompt_path": "prompt.txt",
                        "schema_path": "schema.json",
                        "provider": "dummy",
                        "model": "dummy-model",
                        "timeout": 1,
                        "status": "PASS",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            record_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "audit",
                    "record",
                    "--audit-file",
                    str(audit_file),
                    "--source",
                    str(source_path),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(record_proc.returncode, 0, record_proc.stdout + record_proc.stderr)

            # Deterministic tamper: mutate result status after record was hashed.
            stored = json.loads(audit_file.read_text(encoding="utf-8").splitlines()[0])
            stored["result"]["status"] = "TAMPERED"
            audit_file.write_text(
                json.dumps(stored, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            verify_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "audit",
                    "verify",
                    "--audit-file",
                    str(audit_file),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(verify_proc.returncode, 2, verify_proc.stdout + verify_proc.stderr)
            self.assertIn("AUDIT VERIFY SUMMARY", verify_proc.stdout)
            self.assertIn("invalid=1", verify_proc.stdout)
            self.assertIn("AUDIT FAIL", verify_proc.stdout)
