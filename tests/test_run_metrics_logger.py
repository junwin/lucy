"""RunMetricsLogger tests: append creates/extends the log, no partial line on
failure, missing-field tolerance (issue #131, design doc metrics-report.md)."""

import json

import pytest

from src.message_processors.run_metrics import RunMetrics
from src.metrics import RunMetricsLogger


def test_append_creates_log(tmp_path):
    path = tmp_path / "runs.jsonl"
    logger = RunMetricsLogger(path)
    record = RunMetrics(
        correlation_id="corr-1",
        iterations=3,
        failures=0,
        duration_ms=1234,
        agent="lucy",
        account="junwin",
    )

    logger.append(record)

    assert path.exists()
    lines = path.read_text().splitlines()
    assert len(lines) == 1
    line = lines[0]
    assert line.endswith("\n") is False
    assert json.loads(line) == record.to_dict()
    assert len(line.encode("utf-8")) < 4096


def test_append_extends_log(tmp_path):
    path = tmp_path / "runs.jsonl"
    logger = RunMetricsLogger(path)
    first = RunMetrics(correlation_id="corr-1", iterations=1)
    second = RunMetrics(correlation_id="corr-2", iterations=2, failures=1)

    logger.append(first)
    logger.append(second)

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == first.to_dict()
    assert json.loads(lines[1]) == second.to_dict()


def test_append_no_partial_line_on_failure(tmp_path, monkeypatch):
    import src.metrics.run_metrics_logger as logger_module

    path = tmp_path / "runs.jsonl"
    logger = RunMetricsLogger(path)
    logger.append(RunMetrics(correlation_id="corr-1"))
    before = path.read_text()

    def raise_on_dumps(*args, **kwargs):
        raise RuntimeError("serialization failed")

    monkeypatch.setattr(logger_module.json, "dumps", raise_on_dumps)

    with pytest.raises(RuntimeError):
        logger.append(RunMetrics(correlation_id="corr-2"))

    assert path.read_text() == before


def test_append_missing_field_tolerance(tmp_path):
    path = tmp_path / "runs.jsonl"
    logger = RunMetricsLogger(path)
    record = RunMetrics.from_dict({"correlation_id": "corr-3", "failures": 1})

    logger.append(record)

    parsed = json.loads(path.read_text().splitlines()[0])
    assert parsed["correlation_id"] == "corr-3"
    assert parsed["failures"] == 1
    assert parsed["success"] is True
    assert parsed["prompt_tokens"] == 0
    assert parsed["completion_tokens"] == 0
    assert parsed["total_tokens"] == 0
    assert parsed["agent"] == ""
