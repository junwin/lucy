"""
Standalone topics component (issue #129).

Derived topic index over the append-only event log; topic-partitioned streams
(inbox + one per explicit topic); lifecycle + link events; query/mutation
APIs; migration from named sessions. Built and tested outside the FCP
(decision 4); the FCP consumes through EventStore/TopicStore ABCs in
src/storage/interfaces.py.

Module layout:
  schemas.py    - event envelope, topic_* payloads, stream layout, slug
                  contract (single source of truth)
  streams.py    - inbox + per-topic stream handling
  index.py      - topic projection (derived index)
  mutation.py   - create/rename/link/unlink/merge/archive (append events)
  queries.py    - topic/event queries
  migration.py  - migrate named chat2 sessions into topics

Note: only ``schemas`` is re-exported here on purpose. ``streams.py``,
``index.py``, ``mutation.py`` and ``queries.py`` import ``EventStore`` /
``TopicStore`` from ``src.storage.interfaces``, which itself imports
``src.topics.schemas``; re-exporting those modules from this package root
would create a circular import (storage -> topics -> storage). Import them
directly: ``from src.topics.queries import TopicQueries, TopicStoreImpl``.
"""

from .schemas import (
    EVENT_LOG_SCHEMA_VERSION,
    INBOX_STREAM,
    KIND_CHAT2_EVENT,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    KIND_TOPIC_MERGED,
    KIND_TOPIC_RENAMED,
    KIND_TOPIC_UNLINK,
    MIGRATION_SOURCE_CHAT2,
    SLUG_MAX_LENGTH,
    SLUG_MIN_LENGTH,
    SLUG_PATTERN,
    TOPICS_DIR,
    TOPIC_KINDS,
    Chat2EventPayload,
    EventProvenance,
    TopicArchivedPayload,
    TopicCreatedPayload,
    TopicEvent,
    TopicLinkPayload,
    TopicMergedPayload,
    TopicPayload,
    TopicRecord,
    TopicRenamedPayload,
    TopicUnlinkPayload,
    inbox_path,
    is_valid_slug,
    normalize_slug,
    resolve_slug,
    stream_path,
    validate_slug,
)

__all__ = [
    "EVENT_LOG_SCHEMA_VERSION",
    "INBOX_STREAM",
    "KIND_CHAT2_EVENT",
    "KIND_TOPIC_ARCHIVED",
    "KIND_TOPIC_CREATED",
    "KIND_TOPIC_LINK",
    "KIND_TOPIC_MERGED",
    "KIND_TOPIC_RENAMED",
    "KIND_TOPIC_UNLINK",
    "MIGRATION_SOURCE_CHAT2",
    "SLUG_MAX_LENGTH",
    "SLUG_MIN_LENGTH",
    "SLUG_PATTERN",
    "TOPICS_DIR",
    "TOPIC_KINDS",
    "Chat2EventPayload",
    "EventProvenance",
    "TopicArchivedPayload",
    "TopicCreatedPayload",
    "TopicEvent",
    "TopicLinkPayload",
    "TopicMergedPayload",
    "TopicPayload",
    "TopicRecord",
    "TopicRenamedPayload",
    "TopicUnlinkPayload",
    "inbox_path",
    "is_valid_slug",
    "normalize_slug",
    "resolve_slug",
    "stream_path",
    "validate_slug",
]
