"""Append-only JSONL writer for per-tool-call trace records (issue #204).

One JSONL line per tool call at
``<storage_root>/<storage_namespace>/metrics/tool_calls.jsonl``. The line is the
full ``ToolCallTrace.to_dict()`` serialisation. The log is global, append-only
and is never touched by ``reset_session``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Union

from src.metrics.tool_call_trace import ToolCallTrace


class ToolCallTraceLogger:
    """Appends one ToolCallTrace record per line to the tool call trace log."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def append(self, record: ToolCallTrace) -> None:
        line = json.dumps(record.to_dict(), separators=(",", ":")) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
