"""External regression gate via sentinel test run CLI."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


class TestExternalRegressionGate(unittest.TestCase):
    def test_regression_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            self._write_fake_openai_module(temp_root, '{"name":"John","age":30}')
            _, _, suite_path = self._write_suite_files(
                temp_root=temp_root,
                case_id="c1",
            )
            (temp_root / "snapshots").mkdir(parents=True, exist_ok=True)
            (temp_root / "snapshots" / "c1.json").write_text(
                json.dumps({"name": "John", "age": 30}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                ["python3", "-m", "sentinel.cli", "test", "run", "--suite", str(suite_path)],
                cwd=str(Path(__file__).resolve().parents[2]),
                env={**os.environ, "PYTHONPATH": str(temp_root), "OPENAI_API_KEY": "test-key"},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("TEST SUMMARY", proc.stdout)
            self.assertIn("diff=0", proc.stdout)
            self.assertIn("error=0", proc.stdout)

    def test_regression_diff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp_root = Path(td)
            self._write_fake_openai_module(temp_root, '{"name":"John","age":30}')
            _, _, suite_path = self._write_suite_files(
                temp_root=temp_root,
                case_id="c1",
            )
            (temp_root / "snapshots").mkdir(parents=True, exist_ok=True)
            (temp_root / "snapshots" / "c1.json").write_text(
                json.dumps({"name": "Jane", "age": 99}),
                encoding="utf-8",
            )

            proc = subprocess.run(
                ["python3", "-m", "sentinel.cli", "test", "run", "--suite", str(suite_path)],
                cwd=str(Path(__file__).resolve().parents[2]),
                env={**os.environ, "PYTHONPATH": str(temp_root), "OPENAI_API_KEY": "test-key"},
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("TEST SUMMARY", proc.stdout)
            self.assertIn("diff=1", proc.stdout)
            self.assertRegex(proc.stdout, r"CASE\s+\S+\s+DIFF")

    def _write_suite_files(self, temp_root: Path, case_id: str) -> tuple[Path, Path, Path]:
        prompt_path = temp_root / "prompt.txt"
        schema_path = temp_root / "schema.json"
        suite_path = temp_root / "suite.yaml"

        prompt_path.write_text("Return JSON only.", encoding="utf-8")
        schema_path.write_text(
            json.dumps(
                {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "age": {"type": "number"}},
                    "required": ["name", "age"],
                }
            ),
            encoding="utf-8",
        )
        suite_path.write_text(
            textwrap.dedent(
                f"""
                command: run
                cases:
                  - id: {case_id}
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
        return prompt_path, schema_path, suite_path

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
