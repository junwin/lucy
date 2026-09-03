"""
Topic mutation API (issue #129) - create/rename/link/unlink/merge/archive.

Every operation appends events to the append-only log through the
``EventStore`` (``JsonlEventStore``); existing events are never modified,
moved, or deleted. Re-tagging appends link/unlink events and the index
recomputes; there is no in-place mutation anywhere.

Semantics (pinned 2026-09-01; t-schemas + design/topics.md are the source
of truth):

- ``create_topic``  -> ``topic_created`` {name, slug, description?}; the
  topic's stream is created on the event (streams.py). The slug comes from
  the LLM proposal (decision 8) and is resolved per the slug contract:
  normalized, and on collision a deterministic numeric suffix (``-2``,
  ``-3``, ...) is appended. The ``inbox`` stream name is reserved
  (stream-name collision; guardrail recorded in index.py).
- ``rename_topic``  -> ``topic_renamed`` {old_name, new_name}; **name
  only** - the slug/``topic_id`` is immutable (identity model).
- ``link_events``   -> ``topic_link`` {topic, event_ids, reason?} appended
  to the target topic's stream. Membership changes; events never move.
- ``unlink_events`` -> ``topic_unlink`` {topic, event_ids} appended to the
  target topic's stream.
- ``merge_topics``  -> ``topic_merged`` {source, target} + ``topic_link``
  (source's event ids -> target) appended to the target's stream, then
  ``topic_archived`` appended to the source's stream (freezes it). The
  design's merge sequence has no unlink, so the source keeps its derived ids
  and stays queryable while archived (faithful replay).
- ``archive_topic`` -> ``topic_archived`` {reason?}; the stream freezes
  (event + freeze only; physical copy+marker is out of scope for v1).

Guardrails:

- Events never carry ``topic_id`` (decision 1): the mutation layer never
  puts one on an event; the payload models forbid extra fields.
- ``agent`` is event metadata, never a partition key (decision 7): it is
  recorded on every event; streams are never partitioned by agent.
- No project-context payload, no external refs on topics (decision 9).

The mutation layer keeps a derived ``TopicIndex`` current by applying each
appended event (``apply_event`` - the same code path as replay), so
operations can read current state (slugs, names, membership, archive flags)
without scanning the log. The index is rebuilt per account on first use, so
a fresh ``TopicMutations`` over an existing store sees the full log.

Single-writer assumption: this layer is the only writer in the standalone
component (decision 4). ``rebuild()`` restores truth from the log at any
time. Multi-event operations (merge) are best-effort atomic - a crash
mid-sequence leaves a replayable log; replay is idempotent and
order-independent.
"""

from __future__ import annotations

from typing import List, Optional, Set

from src.storage.interfaces import EventStore
from src.topics.index import TopicIndex
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    KIND_TOPIC_MERGED,
    KIND_TOPIC_RENAMED,
    KIND_TOPIC_UNLINK,
    TopicArchivedPayload,
    TopicCreatedPayload,
    TopicEvent,
    TopicLinkPayload,
    TopicMergedPayload,
    TopicRecord,
    TopicRenamedPayload,
    TopicUnlinkPayload,
    resolve_slug,
)


class TopicError(Exception):
    """Base class for topic mutation errors (issue #129)."""


class TopicNotFoundError(TopicError):
    """Raised when an operation targets a topic that does not exist."""


class TopicArchivedError(TopicError):
    """Raised when an operation targets an archived (frozen) topic.

    Archive = event + freeze (v1); archived topics reject new writes.
    """


class TopicMutations:
    """Topic lifecycle mutations over an ``EventStore`` (issue #129).

    Every method appends at least one event to the log; none of them modify
    existing events. Signatures match the mutation half of the ``TopicStore``
    ABC in ``src/storage/interfaces.py`` (queries.py composes the full
    ``TopicStore``).

    Args:
        store: the append-only event store to write through (``EventStore``
            ABC, implemented by ``JsonlEventStore`` in streams.py).
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

    # ------------------------------------------------------------------
    # Public API (mutation half of TopicStore)
    # ------------------------------------------------------------------

    def create_topic(
        self,
        account: str,
        name: str,
        slug_proposal: str,
        *,
        agent: str,
        description: Optional[str] = None,
    ) -> str:
        """Create an explicit topic; returns the resolved stored slug.

        The slug proposal is a hint (decision 8): the stored slug is the
        deterministic resolution per the slug contract (``resolve_slug``).
        On collision a numeric suffix (``-2``, ``-3``, ...) is appended. The
        ``inbox`` stream name is reserved so a proposal of "inbox" resolves
        to ``inbox-2`` instead of colliding with the inbox stream.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        self._ensure_synced(account)

        existing = set(self._index.topic_ids(account, include_archived=True))
        existing.add(INBOX_STREAM)  # reserve the inbox stream name
        slug = resolve_slug(slug_proposal, existing)

        event = self._event(
            KIND_TOPIC_CREATED,
            TopicCreatedPayload(name=name, slug=slug, description=description),
            account=account,
            stream=slug,
            agent=agent,
        )
        self._append(account, slug, event)
        return slug

    def rename_topic(
        self,
        account: str,
        slug: str,
        new_name: str,
        *,
        agent: str,
    ) -> None:
        """Rename a topic: name only; the slug/``topic_id`` never changes."""
        if not isinstance(new_name, str) or not new_name.strip():
            raise ValueError("new_name must be a non-empty string")
        rec = self._require_active(account, slug)
        event = self._event(
            KIND_TOPIC_RENAMED,
            TopicRenamedPayload(old_name=rec.name, new_name=new_name),
            account=account,
            stream=slug,
            agent=agent,
        )
        self._append(account, slug, event)

    def link_events(
        self,
        account: str,
        slug: str,
        event_ids: List[str],
        *,
        agent: str,
        reason: Optional[str] = None,
    ) -> None:
        """Re-tag event ids into a topic (membership changes; events never move)."""
        self._require_active(account, slug)
        if not event_ids:
            raise ValueError("event_ids must be a non-empty list")
        event = self._event(
            KIND_TOPIC_LINK,
            TopicLinkPayload(topic=slug, event_ids=list(event_ids), reason=reason),
            account=account,
            stream=slug,
            agent=agent,
        )
        self._append(account, slug, event)

    def unlink_events(
        self,
        account: str,
        slug: str,
        event_ids: List[str],
        *,
        agent: str,
    ) -> None:
        """Remove event ids from a topic (append-only re-tagging)."""
        self._require_active(account, slug)
        if not event_ids:
            raise ValueError("event_ids must be a non-empty list")
        event = self._event(
            KIND_TOPIC_UNLINK,
            TopicUnlinkPayload(topic=slug, event_ids=list(event_ids)),
            account=account,
            stream=slug,
            agent=agent,
        )
        self._append(account, slug, event)

    def merge_topics(
        self,
        account: str,
        source: str,
        target: str,
        *,
        agent: str,
    ) -> None:
        """Merge *source* into *target*.

        Appends, in order:
          1. ``topic_merged`` {source, target} -> target's stream
          2. ``topic_link`` (all of source's event ids -> target) ->
             target's stream (skipped when source has no ids; the schema
             requires at least one event id)
          3. ``topic_archived`` -> source's stream (freezes it)

        Events never move: source's ids are re-linked, not copied.
        """
        if source == target:
            raise ValueError("source and target must differ")
        src = self._require_topic(account, source)
        self._require_active(account, target)
        if src.archived:
            raise TopicArchivedError(
                f"source topic {source!r} is archived and cannot be merged"
            )
        ids = self._index.event_ids(account, source)

        self._append(
            account,
            target,
            self._event(
                KIND_TOPIC_MERGED,
                TopicMergedPayload(source=source, target=target),
                account=account,
                stream=target,
                agent=agent,
            ),
        )
        if ids:
            self._append(
                account,
                target,
                self._event(
                    KIND_TOPIC_LINK,
                    TopicLinkPayload(topic=target, event_ids=ids, reason="merge"),
                    account=account,
                    stream=target,
                    agent=agent,
                ),
            )
        self._append(
            account,
            source,
            self._event(
                KIND_TOPIC_ARCHIVED,
                TopicArchivedPayload(reason=f"merged into {target}"),
                account=account,
                stream=source,
                agent=agent,
            ),
        )

    def archive_topic(
        self,
        account: str,
        slug: str,
        *,
        agent: str,
        reason: Optional[str] = None,
    ) -> None:
        """Archive a topic: ``topic_archived`` + freeze (v1: event + freeze only)."""
        rec = self._require_topic(account, slug)
        if rec.archived:
            raise TopicArchivedError(f"topic {slug!r} is already archived")
        event = self._event(
            KIND_TOPIC_ARCHIVED,
            TopicArchivedPayload(reason=reason),
            account=account,
            stream=slug,
            agent=agent,
        )
        self._append(account, slug, event)

    # ------------------------------------------------------------------
    # Index maintenance
    # ------------------------------------------------------------------

    @property
    def index(self) -> TopicIndex:
        """The derived index this mutation layer keeps current."""
        return self._index

    def rebuild(self, account: str) -> None:
        """Rebuild the derived index for *account* from the log (idempotent)."""
        self._index.rebuild(account)
        self._synced.add(account)

    def _ensure_synced(self, account: str) -> None:
        """Rebuild the account's index from the log on first use."""
        if account not in self._synced:
            self._index.rebuild(account)
            self._synced.add(account)

    def _require_topic(self, account: str, slug: str) -> TopicRecord:
        self._ensure_synced(account)
        rec = self._index.get_topic(account, slug)
        if rec is None:
            raise TopicNotFoundError(
                f"topic {slug!r} for account {account!r} does not exist"
            )
        return rec

    def _require_active(self, account: str, slug: str) -> TopicRecord:
        rec = self._require_topic(account, slug)
        if rec.archived:
            raise TopicArchivedError(
                f"topic {slug!r} is archived and rejects new writes"
            )
        return rec

    def _append(self, account: str, stream: str, event: TopicEvent) -> None:
        """Append *event* to the log and apply it to the derived index."""
        self._store.append_event(account, stream, event)
        self._index.apply_event(account, event)

    @staticmethod
    def _event(
        kind: str,
        payload,
        *,
        account: str,
        stream: str,
        agent: str,
    ) -> TopicEvent:
        return TopicEvent(
            kind=kind,
            agent=agent,
            account=account,
            stream=stream,
            payload=payload,
        )


__all__ = [
    "TopicError",
    "TopicNotFoundError",
    "TopicArchivedError",
    "TopicMutations",
]
