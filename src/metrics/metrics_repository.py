"""Read-only query layer over the FCP run metrics log (issue #131, design doc
metrics-report.md).

``MetricsRepository`` reads ``<storage_root>/<storage_namespace>/metrics/runs.jsonl``,
tolerates a missing file, skips malformed or unparseable lines, applies the
supported filters, and returns matching records newest first. ``ended`` is
never stored in a record; it is computed as ``started + duration_ms`` and used
only for time-range filtering. Absent optional fields (e.g. token counts on
non-OpenAI paths) are tolerated through ``RunMetrics`` defaults.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.message_processors.run_metrics import RunMetrics

_Entry = Tuple[datetime, datetime, int, Dict[str, Any]]


def _parse_iso(value: Union[str, datetime]) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    Naive timestamps are assumed to be UTC; a trailing ``Z`` is accepted as a
    UTC designator. Raises ValueError when the value is not parseable.
    """

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"invalid timestamp: {value!r}") from None
    else:
        raise ValueError(f"invalid timestamp: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class MetricsRepository:
    """Reads and filters run records from the metrics runs log."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def query(
        self,
        correlation_id: Optional[str] = None,
        agent: Optional[str] = None,
        account: Optional[str] = None,
        started: Optional[Union[str, datetime]] = None,
        ended: Optional[Union[str, datetime]] = None,
        hit_iteration_cap: Optional[bool] = None,
        success: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Return matching run records, newest first.

        Filters are ANDed; only records that match every provided filter are
        returned. ``started`` matches runs that began at or after the given
        timestamp; ``ended`` matches runs whose computed end (started plus
        duration_ms) is at or before the given timestamp. Invalid timestamps
        raise ValueError. ``limit`` defaults to 50, is clamped to a maximum
        of 500, and must be a positive integer.
        """

        if not isinstance(limit, int) or isinstance(limit, bool):
            raise TypeError("limit must be an integer")
        if limit > 500:
            limit = 500
        elif limit <= 0:
            raise ValueError("limit must be a positive integer")

        started_filter = _parse_iso(started) if started is not None else None
        ended_filter = _parse_iso(ended) if ended is not None else None

        matched = [
            entry
            for entry in self._read_entries()
            if self._matches(
                entry,
                correlation_id=correlation_id,
                agent=agent,
                account=account,
                started_filter=started_filter,
                ended_filter=ended_filter,
                hit_iteration_cap=hit_iteration_cap,
                success=success,
            )
        ]
        matched.sort(key=lambda entry: (entry[0], entry[2]), reverse=True)
        return [entry[3] for entry in matched[:limit]]

    def _read_entries(self) -> List[_Entry]:
        """Read the log into (started, ended, line index, record) tuples.

        A missing file yields no entries; malformed lines and records with an
        unparseable ``started`` are skipped.
        """

        entries: List[_Entry] = []
        try:
            fh = self.path.open("r", encoding="utf-8")
        except FileNotFoundError:
            return entries
        with fh:
            for index, line in enumerate(fh):
                entry = self._parse_entry(line, index)
                if entry is not None:
                    entries.append(entry)
        return entries

    @staticmethod
    def _parse_entry(line: str, index: int) -> Optional[_Entry]:
        """Parse one line into a (started, ended, index, record) tuple.

        Returns None for blank lines, invalid JSON, records that fail
        ``RunMetrics`` validation, and records whose ``started`` cannot be
        parsed.
        """

        line = line.strip()
        if not line:
            return None
        try:
            record = RunMetrics.from_dict(json.loads(line))
        except (TypeError, ValueError):
            return None
        try:
            started_dt = _parse_iso(record.started)
        except ValueError:
            return None
        ended_dt = started_dt + timedelta(milliseconds=record.duration_ms)
        return started_dt, ended_dt, index, record.to_dict()

    @staticmethod
    def _matches(
        entry: _Entry,
        correlation_id: Optional[str],
        agent: Optional[str],
        account: Optional[str],
        started_filter: Optional[datetime],
        ended_filter: Optional[datetime],
        hit_iteration_cap: Optional[bool],
        success: Optional[bool],
    ) -> bool:
        """Return True when the entry satisfies every provided filter."""

        started_dt, ended_dt, _index, record = entry
        if correlation_id is not None and record["correlation_id"] != correlation_id:
            return False
        if agent is not None and record["agent"] != agent:
            return False
        if account is not None and record["account"] != account:
            return False
        if hit_iteration_cap is not None and record["hit_iteration_cap"] != hit_iteration_cap:
            return False
        if success is not None and record["success"] != success:
            return False
        if started_filter is not None and started_dt < started_filter:
            return False
        if ended_filter is not None and ended_dt > ended_filter:
            return False
        return True
