"""MetricsRepository tests: every filter, newest-first ordering, limit
default/clamp, and malformed-line tolerance (issue #131, design doc
metrics-report.md)."""

import json
from datetime import datetime, timezone

import pytest

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


def test_query_returns_records_newest_first(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("mid", "2026-08-27T10:00:00.000Z"),
            _record("old", "2026-08-27T09:00:00.000Z"),
            _record("new", "2026-08-27T11:00:00.000Z"),
        ],
    )

    runs = MetricsRepository(path).query()

    assert _ids(runs) == ["new", "mid", "old"]


def test_newest_first_breaks_ties_by_line_order(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("first-line", "2026-08-27T10:00:00.000Z"),
            _record("second-line", "2026-08-27T10:00:00.000Z"),
        ],
    )

    runs = MetricsRepository(path).query()

    assert _ids(runs) == ["second-line", "first-line"]


def test_filter_by_correlation_id(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("corr-a", "2026-08-27T10:00:00.000Z"),
            _record("corr-b", "2026-08-27T11:00:00.000Z"),
        ],
    )

    runs = MetricsRepository(path).query(correlation_id="corr-b")

    assert _ids(runs) == ["corr-b"]


def test_filter_by_agent(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("a", "2026-08-27T10:00:00.000Z", agent="lucy"),
            _record("b", "2026-08-27T11:00:00.000Z", agent="sage"),
        ],
    )

    runs = MetricsRepository(path).query(agent="sage")

    assert _ids(runs) == ["b"]


def test_filter_by_account(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("a", "2026-08-27T10:00:00.000Z", account="junwin"),
            _record("b", "2026-08-27T11:00:00.000Z", account="other"),
        ],
    )

    runs = MetricsRepository(path).query(account="junwin")

    assert _ids(runs) == ["a"]


def test_filter_by_hit_iteration_cap(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("capped", "2026-08-27T10:00:00.000Z", hit_iteration_cap=True),
            _record("normal", "2026-08-27T11:00:00.000Z", hit_iteration_cap=False),
        ],
    )

    runs = MetricsRepository(path).query(hit_iteration_cap=True)

    assert _ids(runs) == ["capped"]


def test_filter_by_success(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("ok", "2026-08-27T10:00:00.000Z", success=True),
            _record("failed", "2026-08-27T11:00:00.000Z", success=False),
        ],
    )

    runs = MetricsRepository(path).query(success=False)

    assert _ids(runs) == ["failed"]


def test_filter_by_started_time_range(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("early", "2026-08-27T09:00:00.000Z"),
            _record("middle", "2026-08-27T10:00:00.000Z"),
            _record("late", "2026-08-27T11:00:00.000Z"),
        ],
    )

    runs = MetricsRepository(path).query(
        started=datetime(2026, 8, 27, 10, 0, tzinfo=timezone.utc)
    )

    assert _ids(runs) == ["late", "middle"]


def test_started_filter_accepts_iso_string(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("early", "2026-08-27T09:00:00.000Z"),
            _record("late", "2026-08-27T11:00:00.000Z"),
        ],
    )

    runs = MetricsRepository(path).query(started="2026-08-27T10:00:00Z")

    assert _ids(runs) == ["late"]


def test_filter_by_ended_time_range(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("r1", "2026-08-27T10:00:00.000Z", duration_ms=1000),
            _record("r2", "2026-08-27T10:00:00.500Z", duration_ms=1000),
            _record("r3", "2026-08-27T10:01:00.000Z", duration_ms=1000),
        ],
    )

    runs = MetricsRepository(path).query(
        ended=datetime(2026, 8, 27, 10, 0, 1, tzinfo=timezone.utc)
    )

    assert _ids(runs) == ["r1"]


def test_combined_filters(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("a", "2026-08-27T10:00:00.000Z", agent="lucy", success=True),
            _record("b", "2026-08-27T11:00:00.000Z", agent="sage", success=True),
            _record("c", "2026-08-27T12:00:00.000Z", agent="lucy", success=False),
        ],
    )

    runs = MetricsRepository(path).query(agent="lucy", success=False)

    assert _ids(runs) == ["c"]


def test_default_limit_is_50(tmp_path):
    path = tmp_path / "runs.jsonl"
    records = [
        _record(f"c{i:02d}", f"2026-08-27T00:{i:02d}:00.000Z") for i in range(60)
    ]
    _write(path, records)

    runs = MetricsRepository(path).query()

    assert len(runs) == 50
    assert runs[0]["correlation_id"] == "c59"
    assert runs[-1]["correlation_id"] == "c10"


def test_limit_clamped_to_500(tmp_path):
    path = tmp_path / "runs.jsonl"
    records = [
        _record(
            f"c{i:04d}",
            f"2026-08-27T00:{i // 60:02d}:{i % 60:02d}.000Z",
        )
        for i in range(510)
    ]
    _write(path, records)

    repo = MetricsRepository(path)

    assert len(repo.query(limit=1000)) == 500
    assert len(repo.query(limit=501)) == 500
    assert len(repo.query(limit=500)) == 500
    assert repo.query(limit=1000)[0]["correlation_id"] == "c0509"
    assert repo.query(limit=1000)[-1]["correlation_id"] == "c0010"


def test_limit_invalid_raises(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text("")
    repo = MetricsRepository(path)

    with pytest.raises(ValueError):
        repo.query(limit=0)
    with pytest.raises(ValueError):
        repo.query(limit=-3)


def test_malformed_lines_are_skipped(tmp_path):
    path = tmp_path / "runs.jsonl"
    good = _record("good", "2026-08-27T10:00:00.000Z")
    lines = [
        json.dumps(good) + "\n",
        "{not valid json\n",
        "\n",
        "[1, 2, 3]\n",
        json.dumps(
            {
                "correlation_id": "extra-field",
                "started": "2026-08-27T11:00:00.000Z",
                "bogus": 1,
            }
        )
        + "\n",
        json.dumps(
            {
                "correlation_id": "bad-type",
                "started": "2026-08-27T12:00:00.000Z",
                "iterations": "nope",
            }
        )
        + "\n",
        '{"correlation_id": "truncated", "started": "2026-08-27T13:00:00.000Z"',
    ]
    path.write_text("".join(lines))

    runs = MetricsRepository(path).query()

    assert _ids(runs) == ["good"]


def test_missing_file_returns_empty(tmp_path):
    runs = MetricsRepository(tmp_path / "missing.jsonl").query()

    assert runs == []


def test_record_with_unparseable_started_is_skipped(tmp_path):
    path = tmp_path / "runs.jsonl"
    _write(
        path,
        [
            _record("ok", "2026-08-27T10:00:00.000Z"),
            _record("bad", "not-a-date"),
            _record("empty", ""),
        ],
    )

    runs = MetricsRepository(path).query()

    assert _ids(runs) == ["ok"]


def test_absent_optional_fields_tolerated(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text(
        json.dumps(
            {
                "correlation_id": "minimal",
                "started": "2026-08-27T10:00:00.000Z",
                "duration_ms": 500,
                "failures": 0,
            }
        )
        + "\n"
    )

    runs = MetricsRepository(path).query()

    assert len(runs) == 1
    run = runs[0]
    assert run["correlation_id"] == "minimal"
    assert run["prompt_tokens"] == 0
    assert run["completion_tokens"] == 0
    assert run["total_tokens"] == 0
    assert run["success"] is True
    assert run["agent"] == ""


def test_invalid_filter_timestamp_raises(tmp_path):
    path = tmp_path / "runs.jsonl"
    path.write_text("")
    repo = MetricsRepository(path)

    with pytest.raises(ValueError):
        repo.query(started="not-a-date")
