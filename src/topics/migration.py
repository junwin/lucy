"""
Migration from named chat2 sessions into topics (issue #129, review blocker
#3 - implement, not just design).

For each chat2 session (an explicit topic per session, per design/topics.md
"Migration from named sessions"):

1. ``topic_created`` (name = session name; slug resolved per the slug
   contract) - appending it creates the topic's stream (streams.py).
2. The session's events are **copied** into the topic's stream as
   ``chat2_event`` events with **provenance markers** (review gap #3,
   pinned 2026-09-01 in t-schemas): each copy preserves the original
   ``ts`` and ``event_id`` and wraps the original chat2 envelope
   (``role``, ``actor``, ``source_kind``, opaque ``payload``, ``metadata``)
   plus ``EventProvenance`` {source: "chat2", session_id, migrated_at}.
   ``session_id`` stays as **legacy metadata** - it lives in the provenance
   payload, never on the envelope, never as a topic reference (decision 1).
3. ``topic_link`` (all copied event ids -> the topic, reason="migration")
   re-affirms membership explicitly (the design requires link events in
   addition to stream binding).

Idempotency: a re-run skips any session that already has a ``chat2_event``
with ``provenance.session_id == session_id`` in the account's log (scanned
once per run). Slug assignment is deterministic: sessions are processed in
``session_id`` order, and ``create_topic`` resolves collisions with the
deterministic numeric suffix (``-2``, ``-3``, ...) per the slug contract.

Reading is fail-fast and happens **before any write**: all sessions/events
are validated first, so a corrupt legacy file raises ``Chat2ReadError`` and
the log is left untouched (the migration is all-or-nothing at the read
stage). Per-session write errors are recorded in the report and the run
continues; re-running after a fix is safe because completed sessions are
skipped.

Guardrails held:

- Append-only: nothing is ever modified, moved, or deleted; existing events
  are never touched (the old chat2 files and old digests/embeddings stay
  as-is).
- Events never carry ``topic_id`` (decision 1); membership is derived
  (stream binding + ``topic_link``), never stored on the event.
- ``agent`` is event metadata, never a partition key (decision 7): copied
  events carry ``agent="migration"`` (the writer); the original producer is
  preserved in the payload (``role``/``actor``).
- No project-context payload, no external refs (decision 9); no topic
  embeddings (decision 3); old digests/embeddings untouched.

Best-effort atomicity per session (same as the mutation layer): if a crash
interrupts a session mid-write, re-running migrates it under a new suffixed
slug and leaves the partial topic orphaned (merge/archive to clean up).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Set

from src.storage.interfaces import EventStore
from src.topics.index import TopicIndex
from src.topics.mutation import TopicMutations
from src.topics.schemas import (
    KIND_CHAT2_EVENT,
    MIGRATION_SOURCE_CHAT2,
    Chat2EventPayload,
    EventProvenance,
    TopicEvent,
)

#: Subdirectory of the chat2 root that holds one directory per session.
CHAT2_SESSIONS_DIR = "sessions"
#: Per-session metadata file.
CHAT2_META_FILE = "meta.json"
#: Per-session event log (JSON Lines).
CHAT2_EVENTS_FILE = "events.jsonl"

#: Envelope ``agent`` for every event appended by the migration (the writer;
#: the original producer is preserved in the chat2 payload).
MIGRATION_AGENT = "migration"
#: ``topic_link`` reason used by migration.
MIGRATION_LINK_REASON = "migration"


class Chat2MigrationError(Exception):
    """Base class for chat2 migration errors (issue #129)."""


class Chat2ReadError(Chat2MigrationError):
    """Raised when a legacy chat2 session cannot be read/validated.

    Raised during the read stage, before any event is written to the log.
    """


@dataclass
class Chat2EventRecord:
    """One raw event from a legacy chat2 ``events.jsonl``."""

    event_id: str
    ts: datetime
    role: str
    actor: str
    kind: str
    payload: Any
    metadata: dict[str, Any]


@dataclass
class Chat2Session:
    """One legacy chat2 session (meta + events)."""

    session_id: str
    account_name: str
    name: str
    events: List[Chat2EventRecord] = field(default_factory=list)


@dataclass
class Chat2Scan:
    """Result of scanning the chat2 root for one account."""

    sessions: List[Chat2Session] = field(default_factory=list)
    #: Session dirs whose meta.json names a different account.
    other_account: int = 0
    #: Session dirs with missing/corrupt meta.json (not sessions).
    unreadable: int = 0


@dataclass
class MigrationReport:
    """Outcome of one ``TopicMigrator.migrate`` run."""

    #: Session ids migrated in this run (in processing order).
    migrated: List[str] = field(default_factory=list)
    #: Session ids already migrated by a previous run (idempotent skip).
    skipped: List[str] = field(default_factory=list)
    #: Session dirs scanned but owned by another account.
    other_account: int = 0
    #: Session dirs that were not readable (missing/corrupt meta.json).
    unreadable: int = 0
    #: Per-session write errors: "session_id: message".
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when every scanned session either migrated or was skipped."""
        return not self.errors


# ---------------------------------------------------------------------------
# Reading chat2 sessions (validated up front, before any write)
# ---------------------------------------------------------------------------


def scan_chat2_sessions(
    chat2_root: Path | str,
    *,
    account: str,
) -> Chat2Scan:
    """Scan the chat2 root for *account*'s sessions; validate; sort.

    Layout: ``<chat2_root>/sessions/<session_id>/meta.json`` +
    ``events.jsonl``. A directory without a parseable ``meta.json`` counts as
    unreadable (skipped). Sessions whose ``account_name`` differs from
    *account* are counted as other-account (skipped). A corrupt
    ``events.jsonl`` raises ``Chat2ReadError`` before anything is written.

    Sessions are returned sorted by ``session_id`` so slug resolution is
    deterministic across runs.
    """
    root = Path(chat2_root)
    sessions_dir = root / CHAT2_SESSIONS_DIR
    scan = Chat2Scan()
    if not sessions_dir.is_dir():
        return scan

    for session_dir in sorted(sessions_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        meta_path = session_dir / CHAT2_META_FILE
        if not meta_path.is_file():
            scan.unreadable += 1
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            scan.unreadable += 1
            continue
        if not isinstance(meta, dict):
            scan.unreadable += 1
            continue

        session_id = meta.get("session_id") or session_dir.name
        if not isinstance(session_id, str) or not session_id:
            scan.unreadable += 1
            continue
        account_name = meta.get("account_name")
        if account_name != account:
            scan.other_account += 1
            continue

        name = str(meta.get("friendly_name") or "").strip() or session_id
        events = _read_events(session_dir / CHAT2_EVENTS_FILE, session_id=session_id)
        scan.sessions.append(
            Chat2Session(
                session_id=session_id,
                account_name=account_name,
                name=name,
                events=events,
            )
        )

    scan.sessions.sort(key=lambda s: s.session_id)
    return scan


def _read_events(path: Path, *, session_id: str) -> List[Chat2EventRecord]:
    """Parse a chat2 ``events.jsonl`` into records.

    Missing file -> empty list (a session with no events). A malformed line
    raises ``Chat2ReadError`` naming the session and line - the log is left
    untouched because scanning happens before any write.
    """
    if not path.is_file():
        return []
    records: List[Chat2EventRecord] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except ValueError as exc:
            raise Chat2ReadError(
                f"session {session_id}: {path.name} line {lineno}: invalid JSON: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise Chat2ReadError(
                f"session {session_id}: {path.name} line {lineno}: not a JSON object"
            )

        event_id = raw.get("event_id")
        ts_raw = raw.get("ts")
        if not isinstance(event_id, str) or not event_id:
            raise Chat2ReadError(
                f"session {session_id}: {path.name} line {lineno}: missing event_id"
            )
        if not isinstance(ts_raw, str) or not ts_raw:
            raise Chat2ReadError(
                f"session {session_id}: {path.name} line {lineno}: missing ts"
            )
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError as exc:
            raise Chat2ReadError(
                f"session {session_id}: {path.name} line {lineno}: "
                f"invalid ts {ts_raw!r}: {exc}"
            ) from exc

        metadata = raw.get("metadata")
        records.append(
            Chat2EventRecord(
                event_id=event_id,
                ts=ts,
                role=str(raw.get("role") or ""),
                actor=str(raw.get("actor") or ""),
                kind=str(raw.get("kind") or ""),
                payload=raw.get("payload"),
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )
    return records


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TopicMigrator:
    """Migrate legacy chat2 sessions into topics (issue #129).

    Args:
        store: the append-only event store to write through (``EventStore``
            ABC, implemented by ``JsonlEventStore`` in streams.py).
        index: optional shared derived index. Defaults to a fresh
            ``TopicIndex`` over *store* (rebuilt from the log on first use).
        agent: envelope ``agent`` for every appended event (the writer).
            Defaults to ``"migration"``.
    """

    def __init__(
        self,
        store: EventStore,
        index: Optional[TopicIndex] = None,
        *,
        agent: str = MIGRATION_AGENT,
    ) -> None:
        self._store = store
        self._mutations = TopicMutations(store, index)
        self._agent = agent

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def migrate(self, chat2_root: Path | str, account: str) -> MigrationReport:
        """Migrate *account*'s chat2 sessions into topics; idempotent.

        Sessions are scanned and validated first (nothing is written if the
        input is corrupt). Already-migrated sessions are skipped. Returns a
        ``MigrationReport`` describing what happened.
        """
        scan = scan_chat2_sessions(chat2_root, account=account)
        already = self._migrated_session_ids(account)

        report = MigrationReport(
            other_account=scan.other_account,
            unreadable=scan.unreadable,
        )
        for session in scan.sessions:
            if session.session_id in already:
                report.skipped.append(session.session_id)
                continue
            try:
                self._migrate_session(account, session)
            except Chat2MigrationError as exc:
                report.errors.append(f"{session.session_id}: {exc}")
            except ValueError as exc:
                report.errors.append(f"{session.session_id}: {exc}")
            else:
                report.migrated.append(session.session_id)
        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _migrate_session(self, account: str, session: Chat2Session) -> str:
        """Migrate one session; returns the resolved topic slug.

        Sequence: ``topic_created`` (creates the stream) -> one
        ``chat2_event`` copy per session event (provenance-marked) ->
        ``topic_link`` with all copied event ids (skipped when the session
        has no events; the schema requires at least one id).
        """
        slug = self._mutations.create_topic(
            account,
            session.name,
            session.name,
            agent=self._agent,
        )
        migrated_at = datetime.now(timezone.utc)
        for record in session.events:
            event = self._to_topic_event(account, slug, record, session.session_id, migrated_at)
            self._store.append_event(account, slug, event)
        if session.events:
            self._mutations.link_events(
                account,
                slug,
                [r.event_id for r in session.events],
                agent=self._agent,
                reason=MIGRATION_LINK_REASON,
            )
        return slug

    def _to_topic_event(
        self,
        account: str,
        slug: str,
        record: Chat2EventRecord,
        session_id: str,
        migrated_at: datetime,
    ) -> TopicEvent:
        """Wrap a legacy chat2 event as a provenance-marked ``chat2_event``.

        The original ``ts`` and ``event_id`` are preserved on the envelope
        (event-date filtering keeps working on historical events); the
        original envelope fields live in the payload; ``session_id`` is
        legacy metadata inside ``provenance`` - never a topic reference
        (decision 1).
        """
        return TopicEvent(
            ts=record.ts,
            event_id=record.event_id,
            kind=KIND_CHAT2_EVENT,
            agent=self._agent,
            account=account,
            stream=slug,
            payload=Chat2EventPayload(
                role=record.role,
                actor=record.actor,
                source_kind=record.kind,
                payload=record.payload,
                metadata=record.metadata,
                provenance=EventProvenance(
                    source=MIGRATION_SOURCE_CHAT2,
                    session_id=session_id,
                    migrated_at=migrated_at,
                ),
            ),
        )

    def _migrated_session_ids(self, account: str) -> Set[str]:
        """Session ids already migrated: provenance markers in the log.

        Scans every stream once per run (correctness first; an id->event
        lookup index is a later scale optimization).
        """
        migrated: Set[str] = set()
        for stream in self._store.list_streams(account):
            for event in self._store.stream_events(account, stream):
                if event.kind == KIND_CHAT2_EVENT:
                    provenance = event.payload.provenance
                    if provenance.source == MIGRATION_SOURCE_CHAT2:
                        migrated.add(provenance.session_id)
        return migrated


__all__ = [
    "Chat2MigrationError",
    "Chat2ReadError",
    "Chat2EventRecord",
    "Chat2Session",
    "Chat2Scan",
    "MigrationReport",
    "TopicMigrator",
    "scan_chat2_sessions",
    "MIGRATION_AGENT",
    "MIGRATION_LINK_REASON",
]
