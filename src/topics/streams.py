"""
Topic stream handling (issue #129) - the EventStore seam over JSONL files.

Implements ``EventStore`` (``src/storage/interfaces.py``) with account-scoped
JSONL stream files resolved under a data root (the same data root as
tasklists, per design/topics.md):

    <data_root>/topics/<account>/inbox.jsonl        (default destination)
    <data_root>/topics/<account>/<slug>.jsonl       (one per explicit topic)

Rules pinned here (per design/topics.md and src/topics/schemas.py):

- **Inbox is the default destination** for unattributed events. The inbox
  file is created on first write; it is never created up front and it is
  never archived.
- **A topic stream is created on ``topic_created``**: appending a
  ``topic_created`` event for slug X auto-creates ``<X>.jsonl`` and the event
  itself lands in that new stream (lifecycle events live in the topic's
  stream, per topics.md). Appending to any other unknown stream raises
  ``StreamNotFoundError``.
- **Archived topics reject new writes**: appending ``topic_archived`` to a
  topic stream freezes it; every later append raises ``StreamArchivedError``.
  Archive = event + freeze only (physical copy+marker is out of scope for
  v1). Existing events stay queryable.
- **Placement is a storage decision; membership is derived** (decision 1).
  The store only decides where bytes land - it never interprets a stream as
  topic membership, and events never move. The envelope's ``stream`` field is
  physical placement at write time, so it must match the stream being
  written (enforced in ``append_event``).
- **Agent is event metadata, never a partition key** (decision 7). The store
  never reads ``event.agent`` for placement; any agent's events append to the
  same stream file.
- **Append-only**: the store only appends lines to stream files. Nothing is
  ever updated, deleted, or rewritten.

Standalone (decision 4): no FCP/agent imports; the FCP consumes this through
the ``EventStore`` ABC when integrated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from src.storage.interfaces import EventStore
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    KIND_TOPIC_MERGED,
    KIND_TOPIC_UNLINK,
    TopicEvent,
    inbox_path,
    stream_path,
)


class StreamError(Exception):
    """Base class for topic stream errors (issue #129)."""


class StreamNotFoundError(StreamError):
    """Raised when appending to a stream that does not exist.

    Streams come into existence only via ``topic_created`` (or an explicit
    ``create_stream`` call); an unknown stream name is a bug upstream.
    """


class StreamArchivedError(StreamError):
    """Raised when appending to an archived (frozen) topic stream.

    Archive = event + freeze (v1); the stream rejects new writes and stays
    queryable.
    """


class JsonlEventStore(EventStore):
    """JSONL-backed ``EventStore`` for topic streams (issue #129).

    Args:
        data_root: root directory under which ``topics/<account>/`` lives
            (the same data root as tasklists).
    """

    def __init__(self, data_root: Path | str) -> None:
        self._data_root = Path(data_root)
        # (account, stream) -> archived. Derived from the log (a trailing
        # topic_archived event), cached per stream; survives restarts.
        self._archived: dict[tuple[str, str], bool] = {}

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def _path(self, account: str, stream: str) -> Path:
        # stream_path validates account/stream (StoreKey rules: no leading
        # '/', no '..') and yields topics/<account>/<stream>.jsonl.
        return self._data_root / stream_path(account, stream)

    def _account_dir(self, account: str) -> Path:
        # inbox_path validates the account name; parent is topics/<account>.
        return self._data_root / Path(inbox_path(account)).parent

    # ------------------------------------------------------------------
    # EventStore
    # ------------------------------------------------------------------

    def append_event(self, account: str, stream: str, event: TopicEvent) -> TopicEvent:
        """Append *event* to *stream*, creating the file when required.

        - Inbox: created on first write (default destination).
        - ``topic_created`` for slug X: creates stream X, event lands in it.
        - Any other unknown stream: ``StreamNotFoundError``.
        - Archived stream: ``StreamArchivedError``.
        """
        if not isinstance(event, TopicEvent):
            raise TypeError(f"event must be a TopicEvent, got {type(event).__name__}")
        path = self._path(account, stream)
        self._check_envelope_consistency(account, stream, event)

        if stream == INBOX_STREAM:
            # Inbox is the default destination: created on first write.
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
            _append_line(path, event)
            return event

        if not path.exists():
            if event.kind == KIND_TOPIC_CREATED:
                # Creating an explicit topic creates its stream; the
                # topic_created event itself lives in the new stream.
                self.create_stream(account, stream)
            else:
                raise StreamNotFoundError(
                    f"stream {stream!r} for account {account!r} does not exist "
                    "(streams are created on topic_created)"
                )
        elif self._is_archived(account, stream):
            raise StreamArchivedError(
                f"stream {stream!r} for account {account!r} is archived and "
                "rejects new writes"
            )

        _append_line(path, event)
        if event.kind == KIND_TOPIC_ARCHIVED:
            # Archive = event + freeze: the event itself is the trigger.
            self._archived[(account, stream)] = True
        return event

    def stream_events(self, account: str, stream: str) -> Iterator[TopicEvent]:
        """Yield events from a stream in append order (oldest first)."""
        path = self._path(account, stream)
        if not path.exists():
            return
        for line in _iter_lines(path):
            line = line.strip()
            if not line:
                continue
            yield TopicEvent.model_validate_json(line)

    def read_events(
        self,
        account: str,
        stream: str,
        *,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[TopicEvent]:
        """Read events from a stream with optional time bounds and a cap."""
        events = list(self.stream_events(account, stream))
        if start_ts is not None:
            start_ts = _as_utc(start_ts)
            events = [e for e in events if e.ts >= start_ts]
        if end_ts is not None:
            end_ts = _as_utc(end_ts)
            events = [e for e in events if e.ts <= end_ts]
        if limit is not None:
            events = events[:limit]
        return events

    # ------------------------------------------------------------------
    # Stream management
    # ------------------------------------------------------------------

    def create_stream(self, account: str, stream: str) -> None:
        """Create a topic stream file. Idempotent; rejects the inbox.

        The inbox is not created here - it comes into existence on first
        write (``append_event``).
        """
        if stream == INBOX_STREAM:
            raise ValueError(
                "inbox is created on first write, not via create_stream"
            )
        path = self._path(account, stream)  # validates names (StoreKey rules)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()

    def stream_exists(self, account: str, stream: str) -> bool:
        """Return True if the stream file exists for the account."""
        return self._path(account, stream).exists()

    def list_streams(self, account: str) -> List[str]:
        """Return stream names (sorted) for an account, or [] if none.

        Includes the inbox (once written) and every explicit topic stream.
        """
        account_dir = self._account_dir(account)
        if not account_dir.is_dir():
            return []
        return sorted(
            p.name[: -len(".jsonl")]
            for p in account_dir.iterdir()
            if p.is_file() and p.name.endswith(".jsonl")
        )

    def is_archived(self, account: str, stream: str) -> bool:
        """Return True if the stream is archived (frozen against writes)."""
        return self._is_archived(account, stream)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _check_envelope_consistency(
        self, account: str, stream: str, event: TopicEvent
    ) -> None:
        """Keep the envelope honest: placement fields must match the target.

        ``stream`` on the envelope is physical placement at write time, so it
        must equal the stream being written. Topic-referencing payloads must
        target the stream they are appended to (link/unlink/merge go to the
        target topic's stream; topic_created goes to its own new stream).
        """
        if event.account != account:
            raise ValueError(
                f"event.account {event.account!r} does not match account {account!r}"
            )
        if event.stream != stream:
            raise ValueError(
                f"event.stream {event.stream!r} does not match stream {stream!r} "
                "(stream on the envelope is physical placement at write time)"
            )
        payload = event.payload
        if event.kind == KIND_TOPIC_CREATED and payload.slug != stream:
            raise ValueError(
                f"topic_created.slug {payload.slug!r} must match the stream {stream!r}"
            )
        if event.kind == KIND_TOPIC_MERGED and payload.target != stream:
            raise ValueError(
                f"topic_merged.target {payload.target!r} must match the stream {stream!r}"
            )
        if event.kind in (KIND_TOPIC_LINK, KIND_TOPIC_UNLINK) and payload.topic != stream:
            raise ValueError(
                f"{event.kind}.topic {payload.topic!r} must match the stream {stream!r}"
            )

    def _is_archived(self, account: str, stream: str) -> bool:
        """Derive archive state from the log (last event wins), cached.

        Writes are rejected once archived, so the log cannot contain events
        after a ``topic_archived``; scanning the stream's events for a
        trailing ``topic_archived`` is therefore exact.
        """
        if stream == INBOX_STREAM:
            return False
        key = (account, stream)
        if key in self._archived:
            return self._archived[key]
        archived = False
        path = self._path(account, stream)
        if path.exists():
            for line in _iter_lines(path):
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = TopicEvent.model_validate_json(line)
                except Exception:
                    continue
                if ev.kind == KIND_TOPIC_ARCHIVED:
                    archived = True
        self._archived[key] = archived
        return archived


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append_line(path: Path, event: TopicEvent) -> None:
    """Append one JSON line; creates parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")
        f.flush()


def _iter_lines(path: Path) -> Iterator[str]:
    """Yield raw lines from a JSONL file."""
    with open(path, "r", encoding="utf-8") as f:
        yield from f


def _as_utc(dt: datetime) -> datetime:
    """Normalize a bound to timezone-aware UTC (naive assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


__all__ = [
    "StreamError",
    "StreamNotFoundError",
    "StreamArchivedError",
    "JsonlEventStore",
]
