"""
Topic query API (issue #129) - read-only projections over the event log.

The query half of the ``TopicStore`` ABC (``src/storage/interfaces.py``):
``TopicMutations`` (mutation.py) is the write half, and ``TopicStoreImpl``
below composes both into a full ``TopicStore`` over one shared derived index.

Queries are derived, never stored:

- ``get_topic``        -> the derived topic record by slug, incl. ``event_ids``
- ``list_topics``      -> topic records, archived excluded by default,
                          optionally filtered by kind (``explicit`` only in v1)
- ``topics_by_kind``   -> same partition, explicit entry point (DoD: correct
                          partition for explicit vs archived)
- ``events_in_topic``  -> the topic's member events, **newest first**, with an
                          optional ``limit`` and an inclusive event-date range
                          (``[start_ts, end_ts]``) for prompt-builder
                          regulation (decision 5)

Event-date filtering is the v1 answer for time-scoped questions (decision 5):
temporal topics are deferred, so queries filter by the event's ``ts`` with an
inclusive range. There is **no semantic search here** (decision 3): topic
discovery goes through digest embeddings, so this module never touches
embeddings - events in a topic are resolved by the derived index, not by
vector similarity.

Guardrails held:

- Events never carry ``topic_id`` (decision 1): membership comes from the
  derived index, never from events.
- ``agent`` is event metadata, never a partition key (decision 7): queries
  never filter by agent; any agent's events appear in a shared topic.
- Archived topics stay queryable (v1 archive = event + freeze): ``get_topic``
  and ``events_in_topic`` still work for archived topics; only active-topic
  listing excludes them.
- No project-context payload or external refs (decision 9); no topic
  embeddings (decision 3).

Event resolution: the index stores event **ids**; ``events_in_topic``
resolves them to actual ``TopicEvent`` objects by scanning the account's
streams once per account (cached, refreshed after every mutation through the
composed store, or via ``rebuild``). An id→event lookup index is a scale
optimization for later (compaction work); correctness first in v1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from src.storage.interfaces import EventStore, TopicStore
from src.topics.index import TopicIndex
from src.topics.mutation import TopicMutations
from src.topics.schemas import TopicEvent, TopicRecord


class TopicQueries:
    """Query half of ``TopicStore``: derived, read-only projections.

    Args:
        store: the append-only event store to replay (``EventStore`` ABC,
            implemented by ``JsonlEventStore`` in streams.py).
        index: optional shared derived index. Defaults to a fresh
            ``TopicIndex`` over *store*; the account's index is rebuilt from
            the log on first use and kept current incrementally.
    """

    def __init__(
        self,
        store: EventStore,
        index: Optional[TopicIndex] = None,
    ) -> None:
        self._store = store
        self._index = index if index is not None else TopicIndex(store)
        self._synced: Set[str] = set()
        # account -> {event_id: TopicEvent}. Derived by scanning the account's
        # streams; refreshed after mutations (composed store) or via rebuild.
        self._events: Dict[str, Dict[str, TopicEvent]] = {}

    # ------------------------------------------------------------------
    # Topics
    # ------------------------------------------------------------------

    def get_topic(self, account: str, slug: str) -> Optional[TopicRecord]:
        """Return the derived topic record by slug, or None if it does not exist.

        The record includes the derived ``event_ids`` (decision 1: membership
        is derived, never stored on events). Archived topics are returned too
        - existing events stay queryable (v1 archive = event + freeze).
        """
        self._ensure_synced(account)
        return self._index.get_topic(account, slug)

    def list_topics(
        self,
        account: str,
        *,
        kind: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[TopicRecord]:
        """List topic records, optionally filtered by kind.

        By default only **active** topics are returned: archived topics are
        excluded from active-topic queries (lifecycle semantics). ``kind`` is
        ``explicit`` in v1 (decisions 5, 8); temporal/inferred kinds return an
        empty list until Phase 2 / the future state.
        """
        self._ensure_synced(account)
        if kind is None:
            return self._index.list_topics(account, include_archived=include_archived)
        return self._index.topics_by_kind(
            account, kind, include_archived=include_archived
        )

    def topics_by_kind(
        self,
        account: str,
        kind: str,
        *,
        include_archived: bool = False,
    ) -> List[TopicRecord]:
        """List topic records of a given kind (``explicit`` / future kinds).

        Explicit entry point for the DoD partition check (explicit vs
        archived): active explicit topics by default; ``include_archived=True``
        includes archived ones.
        """
        return self.list_topics(account, kind=kind, include_archived=include_archived)

    def topic_ids(self, account: str, *, include_archived: bool = False) -> List[str]:
        """Return the sorted slugs of the (active by default) topics."""
        self._ensure_synced(account)
        return self._index.topic_ids(account, include_archived=include_archived)

    def is_archived(self, account: str, slug: str) -> bool:
        """Return True if the topic is archived (frozen), False otherwise."""
        self._ensure_synced(account)
        return self._index.is_archived(account, slug)

    # ------------------------------------------------------------------
    # Events in a topic
    # ------------------------------------------------------------------

    def events_in_topic(
        self,
        account: str,
        slug: str,
        *,
        limit: Optional[int] = None,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> List[TopicEvent]:
        """Return the topic's member events, **newest first**.

        - ``limit``: cap on the number of events returned (after filtering and
          sorting). Must be a positive int when given.
        - ``start_ts`` / ``end_ts``: inclusive event-date range on the event's
          ``ts`` (decision 5, prompt-builder regulation). Naive datetimes are
          assumed UTC, matching the event envelope.
        - Archived topics are still queryable (existing events stay readable).

        Resolution: the index yields the derived member event ids; the actual
        events are resolved from the account's streams (any stream - members
        can be re-tagged from the inbox or another topic; events never move).
        Lifecycle events are never members, so they never appear here.
        """
        self._ensure_synced(account)
        if limit is not None:
            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
                raise ValueError("limit must be a positive int or None")
        ids = self._index.event_ids(account, slug)
        if not ids:
            return []
        events = self._events.get(account, {})
        # Dangling ids (referenced but not yet in the log) are skipped: the
        # log is the source of truth; a rebuild/refresh picks them up.
        resolved = [events[eid] for eid in ids if eid in events]

        if start_ts is not None or end_ts is not None:
            start = _as_utc(start_ts) if start_ts is not None else None
            end = _as_utc(end_ts) if end_ts is not None else None
            resolved = [
                e
                for e in resolved
                if (start is None or e.ts >= start) and (end is None or e.ts <= end)
            ]

        # Newest first; deterministic tie-break by event_id (descending).
        resolved.sort(key=lambda e: (e.ts, e.event_id), reverse=True)
        if limit is not None:
            resolved = resolved[:limit]
        return resolved

    def event_ids(self, account: str, slug: str) -> List[str]:
        """Return the derived membership (sorted) for a topic, or [] if unknown."""
        self._ensure_synced(account)
        return self._index.event_ids(account, slug)

    # ------------------------------------------------------------------
    # Index / cache maintenance
    # ------------------------------------------------------------------

    @property
    def index(self) -> TopicIndex:
        """The derived index this query layer reads from."""
        return self._index

    def rebuild(self, account: str) -> None:
        """Rebuild the index and the event cache from the log (idempotent)."""
        self._index.rebuild(account)
        self._events[account] = self._scan_events(account)
        self._synced.add(account)

    def refresh(self, account: str) -> None:
        """Re-scan the account's streams into the event cache.

        Called by the composed ``TopicStoreImpl`` after each mutation so newly
        appended events resolve immediately; the shared index is already kept
        current by ``TopicMutations``.
        """
        self._events[account] = self._scan_events(account)
        self._synced.add(account)

    def _ensure_synced(self, account: str) -> None:
        """Rebuild the account's index + event cache from the log on first use."""
        if account not in self._synced:
            self.rebuild(account)

    def _scan_events(self, account: str) -> Dict[str, TopicEvent]:
        """Scan all of the account's streams into an {event_id: event} map.

        The inbox (once written) and every topic stream are scanned; ``agent``
        is never consulted (decision 7) - streams are partitioned by topic.
        """
        mapping: Dict[str, TopicEvent] = {}
        for stream in self._store.list_streams(account):
            for event in self._store.stream_events(account, stream):
                mapping[event.event_id] = event
        return mapping


class TopicStoreImpl(TopicStore):
    """Full ``TopicStore``: mutations + queries over one store and one index.

    Composes ``TopicMutations`` (write half) and ``TopicQueries`` (read half)
    over a single shared derived ``TopicIndex``, so every mutation is
    immediately visible to queries (the query event cache is refreshed after
    each append). Standalone (decision 4): the FCP consumes this through the
    ``TopicStore`` ABC once integrated.

    Args:
        store: the append-only event store to read/write (``EventStore`` ABC,
            implemented by ``JsonlEventStore`` in streams.py).
        index: optional shared derived index. Defaults to a fresh
            ``TopicIndex`` over *store*.
    """

    def __init__(
        self,
        store: EventStore,
        index: Optional[TopicIndex] = None,
    ) -> None:
        self._store = store
        self._index = index if index is not None else TopicIndex(store)
        self._mutations = TopicMutations(store, self._index)
        self._queries = TopicQueries(store, self._index)

    # -- TopicStore ABC: mutations (delegate + refresh the query cache) -------

    def create_topic(
        self,
        account: str,
        name: str,
        slug_proposal: str,
        *,
        agent: str,
        description: Optional[str] = None,
    ) -> str:
        slug = self._mutations.create_topic(
            account, name, slug_proposal, agent=agent, description=description
        )
        self._queries.refresh(account)
        return slug

    def rename_topic(
        self,
        account: str,
        slug: str,
        new_name: str,
        *,
        agent: str,
    ) -> None:
        self._mutations.rename_topic(account, slug, new_name, agent=agent)
        self._queries.refresh(account)

    def link_events(
        self,
        account: str,
        slug: str,
        event_ids: List[str],
        *,
        agent: str,
        reason: Optional[str] = None,
    ) -> None:
        self._mutations.link_events(
            account, slug, event_ids, agent=agent, reason=reason
        )
        self._queries.refresh(account)

    def unlink_events(
        self,
        account: str,
        slug: str,
        event_ids: List[str],
        *,
        agent: str,
    ) -> None:
        self._mutations.unlink_events(account, slug, event_ids, agent=agent)
        self._queries.refresh(account)

    def merge_topics(
        self,
        account: str,
        source: str,
        target: str,
        *,
        agent: str,
    ) -> None:
        self._mutations.merge_topics(account, source, target, agent=agent)
        self._queries.refresh(account)

    def archive_topic(
        self,
        account: str,
        slug: str,
        *,
        agent: str,
        reason: Optional[str] = None,
    ) -> None:
        self._mutations.archive_topic(account, slug, agent=agent, reason=reason)
        self._queries.refresh(account)

    # -- TopicStore ABC: queries -------------------------------------------------

    def get_topic(self, account: str, slug: str) -> Optional[TopicRecord]:
        return self._queries.get_topic(account, slug)

    def list_topics(
        self,
        account: str,
        *,
        kind: Optional[str] = None,
    ) -> List[TopicRecord]:
        return self._queries.list_topics(account, kind=kind)

    # -- Topic query API (design/topics.md: events in topic, topics by kind) -----

    def topics_by_kind(
        self,
        account: str,
        kind: str,
        *,
        include_archived: bool = False,
    ) -> List[TopicRecord]:
        """List topic records of a given kind (explicit vs archived partition)."""
        return self._queries.topics_by_kind(
            account, kind, include_archived=include_archived
        )

    def events_in_topic(
        self,
        account: str,
        slug: str,
        *,
        limit: Optional[int] = None,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> List[TopicEvent]:
        """Return the topic's member events, newest first (decision 5 filter)."""
        return self._queries.events_in_topic(
            account, slug, limit=limit, start_ts=start_ts, end_ts=end_ts
        )

    def event_ids(self, account: str, slug: str) -> List[str]:
        """Return the derived membership (sorted) for a topic, or [] if unknown."""
        return self._queries.event_ids(account, slug)

    def topic_ids(self, account: str, *, include_archived: bool = False) -> List[str]:
        """Return the sorted slugs of the (active by default) topics."""
        return self._queries.topic_ids(account, include_archived=include_archived)

    def is_archived(self, account: str, slug: str) -> bool:
        """Return True if the topic is archived (frozen), False otherwise."""
        return self._queries.is_archived(account, slug)

    # -- Maintenance --------------------------------------------------------------

    @property
    def index(self) -> TopicIndex:
        """The shared derived index (mutations and queries agree on it)."""
        return self._index

    @property
    def mutations(self) -> TopicMutations:
        """The mutation half (write API)."""
        return self._mutations

    @property
    def queries(self) -> TopicQueries:
        """The query half (read API)."""
        return self._queries

    def rebuild(self, account: str) -> None:
        """Rebuild index + event cache from the log (idempotent)."""
        self._mutations.rebuild(account)
        self._queries.rebuild(account)


def _as_utc(dt: datetime) -> datetime:
    """Normalize a bound to timezone-aware UTC (naive assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


__all__ = [
    "TopicQueries",
    "TopicStoreImpl",
]
