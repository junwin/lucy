import json

import pytest

from src.storage.json_file_storage_parts.tasklist_runs import (
    TaskExecutionReader,
    TaskExecutionRecorder,
)


def _record(**overrides):
    rec = {
        "schema_version": 1,
        "record_id": "rec-1",
        "tasklist_key": "tl1",
        "task_id": "task-1",
        "state": "completed",
        "result": {"timestamp": "2026-09-03T00:00:00.000Z", "output": "out"},
    }
    rec.update(overrides)
    return rec


def test_append_twice_writes_two_valid_json_lines(tmp_path):
    runs_path = tmp_path / "tl1.runs.jsonl"
    recorder = TaskExecutionRecorder()

    recorder.append(runs_path, _record(record_id="rec-1", result={"output": "first"}))
    recorder.append(
        runs_path,
        _record(record_id="rec-2", task_id="task-2", result={"output": "multi\nline"}),
    )

    lines = runs_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    parsed = [json.loads(line) for line in lines]
    assert [rec["record_id"] for rec in parsed] == ["rec-1", "rec-2"]
    assert [rec["task_id"] for rec in parsed] == ["task-1", "task-2"]
    assert parsed[1]["result"]["output"] == "multi\nline"


def test_append_rejects_record_missing_record_id_or_task_id(tmp_path):
    runs_path = tmp_path / "tl1.runs.jsonl"
    recorder = TaskExecutionRecorder()

    no_record_id = _record()
    del no_record_id["record_id"]
    with pytest.raises(ValueError):
        recorder.append(runs_path, no_record_id)

    no_task_id = _record()
    del no_task_id["task_id"]
    with pytest.raises(ValueError):
        recorder.append(runs_path, no_task_id)

    assert not runs_path.exists()


def test_append_propagates_oserror_and_creates_no_parent(tmp_path):
    runs_path = tmp_path / "missing_dir" / "tl1.runs.jsonl"
    recorder = TaskExecutionRecorder()

    with pytest.raises(OSError):
        recorder.append(runs_path, _record())

    assert not runs_path.parent.exists()


def test_latest_returns_last_record_for_matching_task_id(tmp_path):
    runs_path = tmp_path / "tl1.runs.jsonl"

    TaskExecutionRecorder.append(
        runs_path, _record(record_id="rec-1", task_id="task-1")
    )
    TaskExecutionRecorder.append(
        runs_path, _record(record_id="rec-2", task_id="task-1")
    )
    TaskExecutionRecorder.append(
        runs_path, _record(record_id="rec-3", task_id="task-2")
    )

    latest = TaskExecutionReader.latest(runs_path, "task-1")
    assert latest["record_id"] == "rec-2"
    assert latest["task_id"] == "task-1"
    assert TaskExecutionReader.latest(runs_path, "task-9") is None


def test_read_all_skips_malformed_middle_line(tmp_path):
    runs_path = tmp_path / "tl1.runs.jsonl"

    TaskExecutionRecorder.append(runs_path, _record(record_id="rec-1", task_id="task-1"))
    with open(runs_path, "a", encoding="utf-8") as f:
        f.write("this is not json\n")
        f.write("[1, 2, 3]\n")
    TaskExecutionRecorder.append(runs_path, _record(record_id="rec-3", task_id="task-2"))

    records = TaskExecutionReader.read_all(runs_path)
    assert [rec["record_id"] for rec in records] == ["rec-1", "rec-3"]


def test_read_all_skips_partial_tail_line_after_crash(tmp_path):
    runs_path = tmp_path / "tl1.runs.jsonl"

    TaskExecutionRecorder.append(runs_path, _record(record_id="rec-1", task_id="task-1"))
    with open(runs_path, "a", encoding="utf-8") as f:
        f.write('{"record_id": "rec-2", "task_id": "task-1", "result": {"output": "crashed')

    assert [rec["record_id"] for rec in TaskExecutionReader.read_all(runs_path)] == [
        "rec-1"
    ]
    assert TaskExecutionReader.latest(runs_path, "task-1")["record_id"] == "rec-1"


def test_read_all_and_latest_handle_empty_and_missing_files(tmp_path):
    empty_path = tmp_path / "empty.runs.jsonl"
    empty_path.write_text("", encoding="utf-8")
    missing_path = tmp_path / "missing.runs.jsonl"

    assert TaskExecutionReader.read_all(empty_path) == []
    assert TaskExecutionReader.latest(empty_path, "task-1") is None
    assert TaskExecutionReader.read_all(missing_path) == []
    assert TaskExecutionReader.latest(missing_path, "task-1") is None
