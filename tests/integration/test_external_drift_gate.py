"""External drift gate via sentinel drift baseline/check CLI."""

from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestExternalDriftGate(unittest.TestCase):
    def test_drift_pass(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            self._write_fake_openai_module(temp_root, '{"payload":{"x":1}}')
            suite_path = self._write_suite(temp_root)
            metrics_path = self._write_metrics(temp_root)
            thresholds_path = self._write_thresholds(temp_root, max_abs_delta=0.0)
            baseline_path = temp_root / "baseline.json"

            baseline_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "drift",
                    "baseline",
                    "--suite",
                    str(suite_path),
                    "--metrics",
                    str(metrics_path),
                    "--output",
                    str(baseline_path),
                ],
                cwd=str(sentinel_root),
                env={**os.environ, "PYTHONPATH": str(temp_root), "OPENAI_API_KEY": "test-key"},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(baseline_proc.returncode, 0, baseline_proc.stdout + baseline_proc.stderr)

            check_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "drift",
                    "check",
                    "--suite",
                    str(suite_path),
                    "--metrics",
                    str(metrics_path),
                    "--baseline",
                    str(baseline_path),
                    "--thresholds",
                    str(thresholds_path),
                ],
                cwd=str(sentinel_root),
                env={**os.environ, "PYTHONPATH": str(temp_root), "OPENAI_API_KEY": "test-key"},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_proc.returncode, 0, check_proc.stdout + check_proc.stderr)
            self.assertIn("DRIFT SUMMARY", check_proc.stdout)
            self.assertIn("fail=0", check_proc.stdout)
            self.assertIn("error=0", check_proc.stdout)

    def test_drift_fail(self) -> None:
        sentinel_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            suite_path = self._write_suite(temp_root)
            metrics_path = self._write_metrics(temp_root)
            thresholds_path = self._write_thresholds(temp_root, max_abs_delta=0.0)
            baseline_path = temp_root / "baseline.json"

            self._write_fake_openai_module(temp_root, '{"payload":{"x":1}}')
            baseline_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "drift",
                    "baseline",
                    "--suite",
                    str(suite_path),
                    "--metrics",
                    str(metrics_path),
                    "--output",
                    str(baseline_path),
                ],
                cwd=str(sentinel_root),
                env={**os.environ, "PYTHONPATH": str(temp_root), "OPENAI_API_KEY": "test-key"},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(baseline_proc.returncode, 0, baseline_proc.stdout + baseline_proc.stderr)

            self._write_fake_openai_module(temp_root, '{"payload":{}}')
            check_proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "sentinel.cli",
                    "drift",
                    "check",
                    "--suite",
                    str(suite_path),
                    "--metrics",
                    str(metrics_path),
                    "--baseline",
                    str(baseline_path),
                    "--thresholds",
                    str(thresholds_path),
                ],
                cwd=str(sentinel_root),
                env={**os.environ, "PYTHONPATH": str(temp_root), "OPENAI_API_KEY": "test-key"},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check_proc.returncode, 1, check_proc.stdout + check_proc.stderr)
            self.assertIn("DRIFT SUMMARY", check_proc.stdout)
            self.assertIn("fail=1", check_proc.stdout)
            self.assertIn("METRIC FAIL", check_proc.stdout)

    def _write_suite(self, temp_root: Path) -> Path:
        prompt_path = temp_root / "prompt.txt"
        schema_path = temp_root / "schema.json"
        suite_path = temp_root / "suite.yaml"

        prompt_path.write_text("Return JSON only.", encoding="utf-8")
        schema_path.write_text(
            '{"type":"object","properties":{"payload":{"type":"object"}},"required":["payload"]}',
            encoding="utf-8",
        )
        suite_path.write_text(
            textwrap.dedent(
                f"""
                command: run
                cases:
                  - id: c1
                    prompt: {prompt_path}
                    schema: {schema_path}
                    provider: openai
                    model: gpt-4.1
                    timeout: 10
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return suite_path

    def _write_metrics(self, temp_root: Path) -> Path:
        metrics_path = temp_root / "metrics.yaml"
        metrics_path.write_text(
            textwrap.dedent(
                """
                metrics:
                  - metric_id: m_key_presence
                    family: object_key_presence
                    path: /payload
                    key: x
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return metrics_path

    def _write_thresholds(self, temp_root: Path, max_abs_delta: float) -> Path:
        thresholds_path = temp_root / "thresholds.yaml"
        thresholds_path.write_text(
            textwrap.dedent(
                f"""
                metric_family:
                  object_key_presence:
                    max_abs_delta: {max_abs_delta}
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        return thresholds_path

    def _write_fake_openai_module(self, temp_root: Path, model_json: str) -> None:
        (temp_root / "openai.py").write_text(
            textwrap.dedent(
                f"""
                class APIConnectionError(Exception):
                    pass

                class APIStatusError(Exception):
                    def __init__(self, status_code=None):
                        super().__init__("status")
                        self.status_code = status_code

                class APITimeoutError(Exception):
                    pass

                class AuthenticationError(Exception):
                    pass

                class BadRequestError(Exception):
                    pass

                class NotFoundError(Exception):
                    pass

                class RateLimitError(Exception):
                    pass


                class _Message:
                    def __init__(self, content):
                        self.content = content


                class _Choice:
                    def __init__(self, content):
                        self.message = _Message(content)


                class _Response:
                    def __init__(self, content):
                        self.id = "fake-id"
                        self.choices = [_Choice(content)]
                        self.usage = None


                class _Completions:
                    def create(self, model, messages, temperature):
                        return _Response({model_json!r})


                class _Chat:
                    def __init__(self):
                        self.completions = _Completions()


                class OpenAI:
                    def __init__(self, api_key, timeout):
                        self.chat = _Chat()
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
