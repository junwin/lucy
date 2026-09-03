"""
Topic projection / derived index (issue #129).

Derives topics from replay of the append-only event log: a topic is a slug
plus a set of event ids (decision 1, t-schemas). The index is a pure
projection - it never writes to the log, never mutates events, and can be
rebuilt at any time.

Membership signals (design/topics.md, "Topic derivation", decision 1):

1. **Stream binding** - non-lifecycle events appended to a topic's own stream
   are members (placement = membership in the common case). In v1 the only
   event kinds are the six ``topic_*`` kinds (schema Literal), so this path
   is dormant until migration/FCP integration introduces conversation kinds;
   the code is forward-compatible and order-independent (events seen before
   their topic's ``topic_created`` are buffered).
2. **Re-tagging** - ``topic_link`` adds event ids; ``topic_unlink`` removes
   them. Membership changes; events never move (no in-place mutation).

Lifecycle semantics (per t-schemas and the pinned lifecycle):

- ``topic_created``  -> the topic record (name, description, created_at)
- ``topic_renamed``  -> name only; the slug/``topic_id`` never changes
- ``topic_merged``   -> the *source* is frozen (archived); its event ids are
  re-linked to the target by the ``topic_link`` events the mutation appends.
  The design's merge sequence has no unlink, so the source keeps its derived
  ids and stays queryable while archived - faithful replay.
- ``topic_archived`` -> ``archived=True``; excluded from active-topic queries
- ``topic_link`` / ``topic_unlink`` -> derived membership deltas

Guardrails:

- Events never carry ``topic_id`` (decision 1); the index derives it.
- ``agent`` is event metadata, never a partition key (decision 7): membership
  never depends on ``event.agent``.
- The inbox is never a topic: a misplaced ``topic_created`` in the inbox
  stream is ignored, and link/unlink events targeting ``inbox`` change
  nothing. The mutation layer must reserve the ``inbox`` slug (stream-name
  collision) - guardrail recorded here for ``t-mutation``.

Rebuild is idempotent: replaying the same log yields the same index whether
the index started empty or with partial state, because ``apply_event`` is the
same code path as replay, event by event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set

from src.storage.interfaces import EventStore
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    KIND_TOPIC_MERGED,
    KIND_TOPIC_RENAMED,
    KIND_TOPIC_UNLINK,
    TopicEvent,
    TopicRecord,
)

KIND_EXPLICIT = "explicit"
KIND_TEMPORAL = "temporal"
KIND_INFERRED = "inferred"

#: Topic record kinds that exist in v1 (decisions 5, 8): explicit only.
V1_KINDS = frozenset({KIND_EXPLICIT})


@dataclass
class _TopicState:
    """Mutable in-memory projection of one topic, rebuilt from the log."""

    topic_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    event_ids: Set[str] = field(default_factory=set)


@dataclass
class _AccountState:
    """Per-account index state (one entry per derived topic)."""

    topics: Dict[str, _TopicState] = field(default_factory=dict)
    # Slugs frozen (merged/archived) before their topic_created was seen.
    # Keeps incremental application order-independent across streams.
    frozen: Set[str] = field(default_factory=set)
    # stream -> event ids seen before the topic existed (forward-compatible
    # stream binding; same order-independence goal).
    pending: Dict[str, Set[str]] = field(default_factory=dict)


class TopicIndex:
    """Derived topic index over an ``EventStore`` (issue #129).

    Args:
        store: the append-only event store to replay (``EventStore`` ABC,
            implemented by ``JsonlEventStore`` in streams.py).
    """

    def __init__(self, store: EventStore) -> None:
        self._store = store
        self._accounts: Dict[str, _AccountState] = {}

    # ------------------------------------------------------------------
    # Build / update
    # ------------------------------------------------------------------

    def rebuild(self, account: str) -> None:
        """Replay the whole log for *account* and rebuild its index.

        Idempotent: starting from empty or from partial state, replaying the
        same log produces the same index.
        """
        state = _AccountState()
        self._accounts[account] = state
        for stream in self._store.list_streams(account):
            for event in self._store.stream_events(account, stream):
                self._apply(state, event, stream)

    def apply_event(self, account: str, event: TopicEvent) -> None:
        """Incrementally apply one event (same code path as replay)."""
        state = self._accounts.setdefault(account, _AccountState())
        self._apply(state, event, event.stream)

    # ------------------------------------------------------------------
    # Queries (the projection)
    # ------------------------------------------------------------------

    def get_topic(self, account: str, topic_id: str) -> Optional[TopicRecord]:
        """Return the topic record by slug, or None if it does not exist.

        Archived topics are returned too - existing events stay queryable
        (v1: archive = event + freeze only).
        """
        state = self._accounts.get(account)
        if state is None:
            return None
        ts = state.topics.get(topic_id)
        if ts is None or ts.name is None:
            return None
        return self._record(ts)

    def list_topics(self, account: str, *, include_archived: bool = False) -> List[TopicRecord]:
        """List topic records sorted by slug.

        By default only **active** topics are returned: archived topics are
        excluded from active-topic queries.
        """
        state = self._accounts.get(account)
        if state is None:
            return []
        records = [
            self._record(ts) for ts in state.topics.values() if ts.name is not None
        ]
        if not include_archived:
            records = [r for r in records if not r.archived]
        return sorted(records, key=lambda r: r.topic_id)

    def topics_by_kind(
        self,
        account: str,
        kind: str,
        *,
        include_archived: bool = False,
    ) -> List[TopicRecord]:
        """List topic records of a given kind (``explicit`` / future kinds).

        v1 only produces ``explicit`` topics (decisions 5, 8); temporal and
        inferred kinds return an empty list until Phase 2 / the future state.
        """
        return [
            r
            for r in self.list_topics(account, include_archived=include_archived)
            if r.kind == kind
        ]

    def event_ids(self, account: str, topic_id: str) -> List[str]:
        """Return the derived membership (sorted) for a topic, or [] if unknown."""
        state = self._accounts.get(account)
        if state is None:
            return []
        ts = state.topics.get(topic_id)
        return sorted(ts.event_ids) if ts is not None else []

    def is_archived(self, account: str, topic_id: str) -> bool:
        """Return True if the topic is archived (frozen), False otherwise."""
        state = self._accounts.get(account)
        if state is None:
            return False
        ts = state.topics.get(topic_id)
        return ts.archived if ts is not None else False

    def topic_ids(self, account: str, *, include_archived: bool = False) -> List[str]:
        """Return the sorted slugs of the (active by default) topics."""
        return [
            r.topic_id
            for r in self.list_topics(account, include_archived=include_archived)
        ]

    # ------------------------------------------------------------------
    # Replay core
    # ------------------------------------------------------------------

    def _apply(self, state: _AccountState, event: TopicEvent, stream: str) -> None:
        kind = event.kind

        if kind == KIND_TOPIC_CREATED:
            # A topic_created in the inbox is misplaced (the store requires it
            # to go to its own stream); ignore it so the inbox can never
            # become a topic. The mutation layer reserves the 'inbox' slug.
            if stream == INBOX_STREAM:
                return
            slug = event.payload.slug
            ts = state.topics.setdefault(slug, _TopicState(topic_id=slug))
            ts.name = event.payload.name
            if event.payload.description is not None:
                ts.description = event.payload.description
            if ts.created_at is None:
                ts.created_at = event.ts
            ts.updated_at = event.ts
            if slug in state.frozen:
                ts.archived = True  # merged/archived before its create was seen
            if slug in state.pending:
                ts.event_ids.update(state.pending.pop(slug))
            return

        if kind == KIND_TOPIC_RENAMED:
            # Renames live in the topic's own stream; name only (slug immutable).
            ts = state.topics.get(stream)
            if ts is not None:
                ts.name = event.payload.new_name
                ts.updated_at = event.ts
            return

        if kind == KIND_TOPIC_MERGED:
            # Source is frozen; its event ids are re-linked to the target by
            # the topic_link events the mutation appends (replayed separately).
            source = event.payload.source
            ts = state.topics.get(source)
            if ts is not None:
                ts.archived = True
                ts.updated_at = event.ts
            else:
                state.frozen.add(source)  # order-independent incremental apply
            return

        if kind == KIND_TOPIC_ARCHIVED:
            # Archive = event + freeze; the stream rejects writes (streams.py),
            # the index just records the flag.
            if stream == INBOX_STREAM:
                return
            ts = state.topics.get(stream)
            if ts is not None:
                ts.archived = True
                ts.updated_at = event.ts
            else:
                state.frozen.add(stream)
            return

        if kind == KIND_TOPIC_LINK:
            ts = state.topics.get(event.payload.topic)
            if ts is not None:
                ts.event_ids.update(event.payload.event_ids)
                ts.updated_at = event.ts
            return

        if kind == KIND_TOPIC_UNLINK:
            ts = state.topics.get(event.payload.topic)
            if ts is not None:
                ts.event_ids.difference_update(event.payload.event_ids)
                ts.updated_at = event.ts
            return

        # Forward-compatible stream binding (decision 1): any non-lifecycle
        # event appended to a topic's own stream is a member (placement =
        # membership in the common case). Dormant in v1 - the schema only
        # defines topic_* kinds; conversation kinds arrive with migration/FCP
        # integration. Inbox events are never members of a topic.
        if stream == INBOX_STREAM:
            return
        ts = state.topics.get(stream)
        if ts is not None:
            ts.event_ids.add(event.event_id)
            ts.updated_at = event.ts
        else:
            state.pending.setdefault(stream, set()).add(event.event_id)

    @staticmethod
    def _record(ts: _TopicState) -> TopicRecord:
        return TopicRecord(
            topic_id=ts.topic_id,
            kind=KIND_EXPLICIT,
            name=ts.name or ts.topic_id,
            description=ts.description,
            archived=ts.archived,
            event_ids=sorted(ts.event_ids),
            created_at=ts.created_at,
            updated_at=ts.updated_at,
        )


__all__ = [
    "KIND_EXPLICIT",
    "KIND_TEMPORAL",
    "KIND_INFERRED",
    "V1_KINDS",
    "TopicIndex",
]
