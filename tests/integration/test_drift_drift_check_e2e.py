"""Integration tests for Drift drift check CLI flow."""

from __future__ import annotations

from pathlib import Path

from sentinel.cli import main
from sentinel.drift.baseline_store import write_baseline
from sentinel.drift.threshold_engine import ThresholdConfig, ThresholdRuleDefinition
from sentinel.drift.types import BaselineEnvelope, MetricFamily, MetricResultRecord


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
            "  - id: c3\n"
            "    prompt: prompt-3.txt\n"
            "    schema: schema-3.json\n"
            "    provider: stub\n"
            "    model: stub\n"
        ),
        encoding="utf-8",
    )


def _write_metrics(path: Path) -> None:
    path.write_text(
        (
            "metrics:\n"
            "  - metric_id: m_numeric\n"
            "    family: numeric\n"
            "    path: /score\n"
        ),
        encoding="utf-8",
    )


def _write_thresholds(path: Path) -> None:
    # Runner consumes monkeypatched threshold object in these tests.
    path.write_text("metric_family:\n  numeric:\n    max_abs_delta: 0.1\n", encoding="utf-8")


def _baseline_for_numeric(path: Path, mean: float, min_val: float, max_val: float) -> None:
    error = write_baseline(
        str(path),
        BaselineEnvelope(
            version="1.0",
            suite="suite.yaml",
            metrics=[
                MetricResultRecord("m_numeric", MetricFamily.NUMERIC, "/score", "max", max_val),
                MetricResultRecord("m_numeric", MetricFamily.NUMERIC, "/score", "mean", mean),
                MetricResultRecord("m_numeric", MetricFamily.NUMERIC, "/score", "min", min_val),
            ],
        ),
    )
    assert error is None


def test_drift_check_pass(tmp_path: Path, monkeypatch, capsys) -> None:
    suite_path = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.yaml"
    thresholds_path = tmp_path / "thresholds.yaml"
    baseline_path = tmp_path / "baseline.json"
    _write_suite(suite_path)
    _write_metrics(metrics_path)
    _write_thresholds(thresholds_path)
    _baseline_for_numeric(baseline_path, mean=2.0, min_val=1.0, max_val=3.0)

    monkeypatch.setattr(
        "sentinel.drift.runner.execute_case",
        lambda case: {"score": {"c1": 1, "c2": 2, "c3": 3}[case.case_id]},
    )
    monkeypatch.setattr(
        "sentinel.drift.runner.load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.0)},
            global_rule=None,
        ),
    )

    exit_code = main(
        [
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
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert out == "DRIFT SUMMARY total_metrics=3 pass=3 fail=0 error=0 cases=3 approved=3\n"


def test_drift_check_fail_and_deterministic_output_ordering(tmp_path: Path, monkeypatch, capsys) -> None:
    suite_path = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.yaml"
    thresholds_path = tmp_path / "thresholds.yaml"
    baseline_path = tmp_path / "baseline.json"
    _write_suite(suite_path)
    _write_metrics(metrics_path)
    _write_thresholds(thresholds_path)
    _baseline_for_numeric(baseline_path, mean=2.0, min_val=1.0, max_val=3.0)

    monkeypatch.setattr(
        "sentinel.drift.runner.execute_case",
        lambda case: {"score": {"c1": 1, "c2": 2, "c3": 4}[case.case_id]},
    )
    monkeypatch.setattr(
        "sentinel.drift.runner.load_thresholds_config",
        lambda _: ThresholdConfig(
            per_key={},
            per_path={},
            metric_family={MetricFamily.NUMERIC: ThresholdRuleDefinition(max_abs_delta=0.1)},
            global_rule=None,
        ),
    )

    exit_code = main(
        [
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
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 1
    assert out == (
        "DRIFT SUMMARY total_metrics=3 pass=1 fail=2 error=0 cases=3 approved=3\n"
        "METRIC FAIL numeric /score m_numeric.max baseline=3.0 current=4.0 delta=1.0 threshold=0.1\n"
        "METRIC FAIL numeric /score m_numeric.mean baseline=2.0 current=2.3333333333333335 delta=0.3333333333333335 threshold=0.1\n"  # noqa: E501
    )


def test_drift_check_error(tmp_path: Path, monkeypatch, capsys) -> None:
    suite_path = tmp_path / "suite.yaml"
    metrics_path = tmp_path / "metrics.yaml"
    thresholds_path = tmp_path / "thresholds.yaml"
    baseline_path = tmp_path / "baseline.json"
    _write_suite(suite_path)
    _write_metrics(metrics_path)
    _write_thresholds(thresholds_path)
    # Baseline intentionally missing m_numeric.max to trigger comparator ERROR.
    error = write_baseline(
        str(baseline_path),
        BaselineEnvelope(
            version="1.0",
            suite="suite.yaml",
            metrics=[
                MetricResultRecord("m_numeric", MetricFamily.NUMERIC, "/score", "mean", 2.0),
                MetricResultRecord("m_numeric", MetricFamily.NUMERIC, "/score", "min", 1.0),
            ],
        ),
    )
    assert error is None

    monkeypatch.setattr(
        "sentinel.drift.runner.execute_case",
        lambda case: {"score": {"c1": 1, "c2": 2, "c3": 3}[case.case_id]},
    )
    monkeypatch.setattr(
        "sentinel.drift.runner.load_thresholds_config",
        lambda _: ThresholdConfig(per_key={}, per_path={}, metric_family={}, global_rule=None),
    )

    exit_code = main(
        [
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
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 2
    assert out == (
        "DRIFT SUMMARY total_metrics=3 pass=2 fail=0 error=1 cases=3 approved=3\n"
        "METRIC ERROR numeric /score m_numeric.max Current metric has no matching baseline metric.\n"
    )
