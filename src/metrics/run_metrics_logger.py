"""Append-only JSONL writer for FCP run metrics records (issue #131).

One JSONL line per run at ``<storage_root>/<storage_namespace>/metrics/runs.jsonl``.
The line is the full ``RunMetrics.to_dict()`` serialisation; optional fields
absent on non-OpenAI paths are tolerated because ``RunMetrics`` supplies
defaults for them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Union

from src.message_processors.run_metrics import RunMetrics


class RunMetricsLogger:
    """Appends one RunMetrics record per line to the metrics runs log."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def append(self, record: RunMetrics) -> None:
        line = json.dumps(record.to_dict(), separators=(",", ":")) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
