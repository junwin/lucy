from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class TaskExecutionRecorder:
    """Appends one execution record per completed or failed task to a runs file."""

    @staticmethod
    def append(runs_path: Path, record: dict) -> None:
        """Append the record as a single JSON line and flush before returning."""
        if "record_id" not in record or "task_id" not in record:
            raise ValueError("record must contain 'record_id' and 'task_id'")
        with open(runs_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()


class TaskExecutionReader:
    """Reads execution records from a runs file, skipping malformed lines."""

    @staticmethod
    def read_all(runs_path: Path) -> list[dict]:
        """Return every parseable record; a missing file yields an empty list."""
        if not runs_path.exists():
            return []
        records = []
        with open(runs_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
        return records

    @staticmethod
    def latest(runs_path: Path, task_id: str) -> Optional[dict]:
        """Return the last record whose task_id matches, else None."""
        match = None
        for record in TaskExecutionReader.read_all(runs_path):
            if record.get("task_id") == task_id:
                match = record
        return match
