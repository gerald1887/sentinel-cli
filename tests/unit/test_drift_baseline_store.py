"""Unit tests for Drift baseline store."""

from __future__ import annotations

from pathlib import Path

from sentinel.core.errors import FILE_NOT_FOUND, FILE_READ_ERROR, SCHEMA_INVALID, SentinelError
from sentinel.drift.baseline_store import read_baseline, write_baseline
from sentinel.drift.types import BASELINE_VERSION, BaselineEnvelope, MetricFamily, MetricResultRecord


def _baseline_fixture() -> BaselineEnvelope:
    return BaselineEnvelope(
        version="1.0",
        suite="suite.yaml",
        metrics=[
            MetricResultRecord(
                metric_id="m_numeric",
                family=MetricFamily.NUMERIC,
                path="/score",
                key="mean",
                value=2.5,
            ),
            MetricResultRecord(
                metric_id="m_presence",
                family=MetricFamily.PRESENCE,
                path="/user/id",
                key="presence_rate",
                value=1.0,
            ),
        ],
    )


def test_write_baseline_success(tmp_path: Path) -> None:
    baseline_path = tmp_path / "drift" / "baseline.json"
    error = write_baseline(str(baseline_path), _baseline_fixture())
    assert error is None
    assert baseline_path.exists()


def test_read_baseline_success(tmp_path: Path) -> None:
    baseline_path = tmp_path / "drift" / "baseline.json"
    write_error = write_baseline(str(baseline_path), _baseline_fixture())
    assert write_error is None

    loaded = read_baseline(str(baseline_path))
    assert isinstance(loaded, BaselineEnvelope)
    assert loaded.version == BASELINE_VERSION
    assert loaded.suite == "suite.yaml"
    assert [(item.metric_id, item.family, item.key, item.value) for item in loaded.metrics] == [
        ("m_numeric", MetricFamily.NUMERIC, "mean", 2.5),
        ("m_presence", MetricFamily.PRESENCE, "presence_rate", 1.0),
    ]


def test_read_baseline_malformed_json_fails(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text("{not json}", encoding="utf-8")
    result = read_baseline(str(baseline_path))
    assert isinstance(result, SentinelError)
    assert result.category == SCHEMA_INVALID
    assert result.code == "SENTINEL_BASELINE_INVALID_JSON"


def test_read_baseline_missing_required_fields_fail(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text('{"version":"1.0","suite":"suite.yaml"}\n', encoding="utf-8")
    result = read_baseline(str(baseline_path))
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_BASELINE_MISSING_METRICS"


def test_read_baseline_invalid_version_fails(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        '{"version":"2.0","suite":"suite.yaml","metrics":[]}\n',
        encoding="utf-8",
    )
    result = read_baseline(str(baseline_path))
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_BASELINE_INVALID_VERSION"
    assert result.details == {
        "path": str(baseline_path),
        "version": "2.0",
        "expected_version": "1.0",
    }


def test_read_baseline_invalid_metric_payload_fails(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        (
            '{"version":"1.0","suite":"suite.yaml","metrics":'
            '[{"metric_id":"m1","family":"numeric","path":"/x","key":"mean","value":"bad"}]}'
            "\n"
        ),
        encoding="utf-8",
    )
    result = read_baseline(str(baseline_path))
    assert isinstance(result, SentinelError)
    assert result.code == "SENTINEL_BASELINE_INVALID_METRIC_VALUE"


def test_write_baseline_deterministic_formatting(tmp_path: Path) -> None:
    baseline_path = tmp_path / "drift" / "baseline.json"
    error = write_baseline(str(baseline_path), _baseline_fixture())
    assert error is None
    text = baseline_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.index('"metrics"') < text.index('"suite"')
    assert text.index('"suite"') < text.index('"version"')
    assert text.index('"family"') < text.index('"key"')
    assert text.index('"key"') < text.index('"metric_id"')
    assert text.index('"metric_id"') < text.index('"path"')
    assert text.index('"path"') < text.index('"value"')


def test_read_baseline_missing_file_is_deterministic(tmp_path: Path) -> None:
    result = read_baseline(str(tmp_path / "missing.json"))
    assert isinstance(result, SentinelError)
    assert result.category == FILE_NOT_FOUND


def test_read_baseline_io_failure_returns_error(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "as_dir"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    result = read_baseline(str(baseline_dir))
    assert isinstance(result, SentinelError)
    assert result.category == FILE_READ_ERROR


def test_write_baseline_io_failure_returns_error(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "cannot_write_here"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    result = write_baseline(str(baseline_dir), _baseline_fixture())
    assert isinstance(result, SentinelError)
    assert result.category == FILE_READ_ERROR
