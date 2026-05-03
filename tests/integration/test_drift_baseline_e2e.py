"""Integration tests for Drift drift baseline CLI flow."""

from __future__ import annotations

import json
from pathlib import Path

from sentinel.cli import main


def _write_suite(path: Path) -> None:
    path.write_text(
        (
            "command: run\n"
            "cases:\n"
            "  - id: c1\n"
            "    prompt: prompt-1.txt\n"
            "    schema: schema-1.json\n"
            "    provider: stub\n"
            "    model: stub\n"
            "  - id: c2\n"
            "    prompt: prompt-2.txt\n"
            "    schema: schema-2.json\n"
            "    provider: stub\n"
            "    model: stub\n"
        ),
        encoding="utf-8",
    )


def _write_metrics(path: Path) -> None:
    path.write_text(
        (
            "metrics:\n"
            "  - metric_id: m_coverage\n"
            "    family: coverage\n"
            "    path: /coverage\n"
            "  - metric_id: m_presence\n"
            "    family: presence\n"
            "    path: /answer\n"
        ),
        encoding="utf-8",
    )


def test_drift_baseline_happy_path_and_deterministic_artifact(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    suite_path = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.yaml"
    baseline_path = tmp_path / "baseline.json"
    _write_suite(suite_path)
    _write_metrics(metrics_path)

    outputs = {
        "c1": {"answer": {"value": 1}},
        "c2": {"answer": {"value": 2}},
    }

    monkeypatch.setattr(
        "sentinel.drift.runner.execute_case",
        lambda case: outputs[case.case_id],
    )

    exit_code_first = main(
        [
            "drift",
            "baseline",
            "--suite",
            str(suite_path),
            "--metrics",
            str(metrics_path),
            "--output",
            str(baseline_path),
        ]
    )
    first_out = capsys.readouterr().out
    first_artifact = baseline_path.read_text(encoding="utf-8")

    exit_code_second = main(
        [
            "drift",
            "baseline",
            "--suite",
            str(suite_path),
            "--metrics",
            str(metrics_path),
            "--output",
            str(baseline_path),
        ]
    )
    second_out = capsys.readouterr().out
    second_artifact = baseline_path.read_text(encoding="utf-8")

    assert exit_code_first == 0
    assert exit_code_second == 0
    assert first_out == second_out == "DRIFT BASELINE SUMMARY total_cases=2 approved=2 errors=0 metrics=8\n"
    assert first_artifact == second_artifact
    assert first_artifact.endswith("\n")

    loaded = json.loads(first_artifact)
    assert loaded["version"] == "1.0"
    assert loaded["suite"] == str(suite_path)
    assert isinstance(loaded["metrics"], list)
