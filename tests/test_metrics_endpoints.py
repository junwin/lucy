"""Tests for the /metrics/runs endpoint implementation (issue #131, design doc
metrics-report.md).

Covers the happy path, every query filter, limit defaulting and clamping, and
HTTP 400 validation for invalid parameter values.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from src.http_endpoints.metrics_endpoints import get_metrics_runs_impl
from src.metrics import MetricsRepository


def _record(
    correlation_id: str,
    started: str,
    duration_ms: int = 0,
    agent: str = "lucy",
    account: str = "junwin",
    hit_iteration_cap: bool = False,
    success: bool = True,
) -> dict:
    return {
        "correlation_id": correlation_id,
        "agent": agent,
        "account": account,
        "session_id": "sess-1",
        "started": started,
        "duration_ms": duration_ms,
        "iterations": 1,
        "max_iterations": 10,
        "hit_iteration_cap": hit_iteration_cap,
        "tool_calls": 0,
        "openai_calls": 0,
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "failures": 0,
        "errors": 0,
        "warnings": 0,
        "success": success,
    }


def _write(path, records):
    lines = [json.dumps(record) + "\n" for record in records]
    path.write_text("".join(lines))


def _ids(runs):
    return [run["correlation_id"] for run in runs]


@pytest.fixture
def log_path(tmp_path):
    """Path to a runs.jsonl log inside the test temp directory."""
    return tmp_path / "runs.jsonl"


def _make_container(repository):
    """Container mock that resolves MetricsRepository via container.get."""
    def _container_get(cls):
        if cls is MetricsRepository:
            return repository
        raise KeyError(cls)

    container = Mock()
    container.get.side_effect = _container_get
    return container


def _call(container, params):
    return get_metrics_runs_impl(container, None, params)


def test_happy_path_returns_all_records_newest_first(log_path):
    _write(
        log_path,
        [
            _record("mid", "2026-08-27T10:00:00.000Z"),
            _record("old", "2026-08-27T09:00:00.000Z"),
            _record("new", "2026-08-27T11:00:00.000Z"),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {})

    assert status == 200
    assert body["count"] == 3
    assert _ids(body["runs"]) == ["new", "mid", "old"]


def test_missing_log_file_returns_empty(log_path):
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {})

    assert status == 200
    assert body == {"count": 0, "runs": []}


def test_filter_by_correlation_id(log_path):
    _write(
        log_path,
        [
            _record("corr-a", "2026-08-27T10:00:00.000Z"),
            _record("corr-b", "2026-08-27T11:00:00.000Z"),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"correlation_id": "corr-b"})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["corr-b"]


def test_filter_by_agent(log_path):
    _write(
        log_path,
        [
            _record("a", "2026-08-27T10:00:00.000Z", agent="lucy"),
            _record("b", "2026-08-27T11:00:00.000Z", agent="sage"),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"agent": "sage"})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["b"]


def test_filter_by_account(log_path):
    _write(
        log_path,
        [
            _record("a", "2026-08-27T10:00:00.000Z", account="junwin"),
            _record("b", "2026-08-27T11:00:00.000Z", account="other"),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"account": "junwin"})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["a"]


def test_filter_by_started(log_path):
    _write(
        log_path,
        [
            _record("early", "2026-08-27T10:00:00.000Z"),
            _record("late", "2026-08-27T11:00:00.000Z"),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"started": "2026-08-27T10:30:00.000Z"})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["late"]


def test_filter_by_ended(log_path):
    _write(
        log_path,
        [
            _record("short", "2026-08-27T10:00:00.000Z", duration_ms=0),
            _record("long", "2026-08-27T10:00:00.000Z", duration_ms=3_600_000),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"ended": "2026-08-27T10:30:00.000Z"})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["short"]


def test_filter_by_hit_iteration_cap(log_path):
    _write(
        log_path,
        [
            _record("capped", "2026-08-27T10:00:00.000Z", hit_iteration_cap=True),
            _record("normal", "2026-08-27T11:00:00.000Z", hit_iteration_cap=False),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"hit_iteration_cap": "true"})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["capped"]


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "1"])
def test_success_filter_accepts_true_forms(log_path, value):
    _write(
        log_path,
        [
            _record("ok", "2026-08-27T10:00:00.000Z", success=True),
            _record("bad", "2026-08-27T11:00:00.000Z", success=False),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"success": value})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["ok"]


@pytest.mark.parametrize("value", ["false", "False", "FALSE", "0"])
def test_success_filter_accepts_false_forms(log_path, value):
    _write(
        log_path,
        [
            _record("ok", "2026-08-27T10:00:00.000Z", success=True),
            _record("bad", "2026-08-27T11:00:00.000Z", success=False),
        ],
    )
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"success": value})

    assert status == 200
    assert body["count"] == 1
    assert _ids(body["runs"]) == ["bad"]


def test_limit_defaults_to_50(log_path):
    records = [
        _record(f"r{i:03d}", f"2026-08-{i // 24 + 1:02d}T{i % 24:02d}:00:00.000Z")
        for i in range(60)
    ]
    _write(log_path, records)
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {})

    assert status == 200
    assert body["count"] == 50
    assert len(body["runs"]) == 50


def test_limit_clamped_to_500(log_path):
    records = [
        _record(f"r{i:03d}", f"2026-08-27T{i % 24:02d}:00:00.000Z")
        for i in range(520)
    ]
    _write(log_path, records)
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"limit": "9999"})

    assert status == 200
    assert body["count"] == 500
    assert len(body["runs"]) == 500


@pytest.mark.parametrize("value", ["abc", "10.5", "1e3"])
def test_limit_non_integer_returns_400(log_path, value):
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"limit": value})

    assert status == 400
    assert "error" in body


@pytest.mark.parametrize("value", ["0", "-5"])
def test_limit_non_positive_returns_400(log_path, value):
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"limit": value})

    assert status == 400
    assert "error" in body


@pytest.mark.parametrize("param", ["started", "ended"])
def test_invalid_timestamp_returns_400(log_path, param):
    _write(log_path, [_record("a", "2026-08-27T10:00:00.000Z")])
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {param: "not-a-timestamp"})

    assert status == 400
    assert "error" in body


def test_invalid_success_returns_400(log_path):
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"success": "maybe"})

    assert status == 400
    assert "error" in body


def test_invalid_hit_iteration_cap_returns_400(log_path):
    container = _make_container(MetricsRepository(log_path))

    body, status = _call(container, {"hit_iteration_cap": "yes"})

    assert status == 400
    assert "error" in body
