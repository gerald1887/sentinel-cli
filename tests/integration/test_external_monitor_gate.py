"""External monitor gate via sentinel monitor record/check CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestExternalMonitorGate(unittest.TestCase):
    def test_monitor_pass(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            source_path = temp_root / "source_pass.json"
            event_file = temp_root / "events.jsonl"
            signals_path = temp_root / "signals.json"
            rules_path = temp_root / "rules_pass.json"

            source_path.write_text(
                json.dumps(
                    {
                        "command": "external.run",
                        "status": "PASS",
                        "exit_code": 0,
                        "duration_ms": 10,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            signals_path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}
                        ]
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            rules_path.write_text(
                json.dumps(
                    {"rules": [{"id": "r_pass", "signal": "pass_count", "operator": "eq", "expected": 1, "message": "ok"}]},  # noqa: E501
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            record_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "monitor",
                    "record",
                    "--event-file",
                    str(event_file),
                    "--source",
                    str(source_path),
                    "--event-type",
                    "external_llm_run",
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(record_proc.returncode, 0, record_proc.stdout + record_proc.stderr)

            check_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "monitor",
                    "check",
                    "--event-file",
                    str(event_file),
                    "--signals",
                    str(signals_path),
                    "--rules",
                    str(rules_path),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_proc.returncode, 0, check_proc.stdout + check_proc.stderr)
            self.assertIn("MONITOR CHECK SUMMARY", check_proc.stdout)
            self.assertIn("fail=0", check_proc.stdout)
            self.assertIn("error=0", check_proc.stdout)

    def test_monitor_fail(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            source_path = temp_root / "source_fail.json"
            event_file = temp_root / "events.jsonl"
            signals_path = temp_root / "signals.json"
            rules_path = temp_root / "rules_fail.json"

            source_path.write_text(
                json.dumps(
                    {
                        "command": "external.run",
                        "status": "FAIL",
                        "exit_code": 1,
                        "duration_ms": 11,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            signals_path.write_text(
                json.dumps(
                    {
                        "signals": [
                            {"name": "pass_count", "type": "count", "options": {"field": "status", "equals": "PASS"}}
                        ]
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            rules_path.write_text(
                json.dumps(
                    {"rules": [{"id": "r_fail", "signal": "pass_count", "operator": "eq", "expected": 1, "message": "must pass"}]},  # noqa: E501
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            record_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "monitor",
                    "record",
                    "--event-file",
                    str(event_file),
                    "--source",
                    str(source_path),
                    "--event-type",
                    "external_llm_run",
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(record_proc.returncode, 0, record_proc.stdout + record_proc.stderr)

            check_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "monitor",
                    "check",
                    "--event-file",
                    str(event_file),
                    "--signals",
                    str(signals_path),
                    "--rules",
                    str(rules_path),
                ],
                cwd=str(sentinel_root),
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_proc.returncode, 1, check_proc.stdout + check_proc.stderr)
            self.assertIn("MONITOR CHECK SUMMARY", check_proc.stdout)
            self.assertIn("fail=1", check_proc.stdout)
            self.assertIn("RULE FAIL", check_proc.stdout)
