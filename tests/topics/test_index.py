"""
Tests for src/topics/index.py - the derived topic index (issue #129).

Covers the t-index DoD:
- replay from empty state and from partial state yields identical topic
  indexes (idempotent)
- re-tagging via link/unlink changes membership without moving any event
- archived topics excluded from active-topic queries
- lifecycle semantics: renamed topics keep their slug, merged topics re-link

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import pytest

from src.storage.interfaces import EventStore
from src.topics.index import (
    KIND_EXPLICIT,
    KIND_INFERRED,
    KIND_TEMPORAL,
    TopicIndex,
)
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
    TopicRenamedPayload,
    TopicUnlinkPayload,
    inbox_path,
    stream_path,
)
from src.topics.streams import JsonlEventStore

ACCOUNT = "junwin"


# ---------------------------------------------------------------------------
# Event builders (within the pinned v1 schema: topic_* kinds only)
# ---------------------------------------------------------------------------


def _event(
    kind: str,
    payload,
    stream: str,
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    ev = TopicEvent(kind=kind, agent=agent, account=ACCOUNT, stream=stream, payload=payload)
    if ts is not None:
        ev.ts = ts
    return ev


def _created(
    slug: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    return _event(
        KIND_TOPIC_CREATED,
        TopicCreatedPayload(name=name or slug, slug=slug, description=description),
        stream=slug,
        agent=agent,
        ts=ts,
    )


def _renamed(
    slug: str,
    old_name: str,
    new_name: str,
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    return _event(
        KIND_TOPIC_RENAMED,
        TopicRenamedPayload(old_name=old_name, new_name=new_name),
        stream=slug,
        agent=agent,
        ts=ts,
    )


def _link(
    slug: str,
    event_ids: List[str],
    reason: Optional[str] = None,
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    return _event(
        KIND_TOPIC_LINK,
        TopicLinkPayload(topic=slug, event_ids=event_ids, reason=reason),
        stream=slug,
        agent=agent,
        ts=ts,
    )


def _unlink(
    slug: str,
    event_ids: List[str],
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    return _event(
        KIND_TOPIC_UNLINK,
        TopicUnlinkPayload(topic=slug, event_ids=event_ids),
        stream=slug,
        agent=agent,
        ts=ts,
    )


def _merged(
    source: str,
    target: str,
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    return _event(
        KIND_TOPIC_MERGED,
        TopicMergedPayload(source=source, target=target),
        stream=target,
        agent=agent,
        ts=ts,
    )


def _archived(
    slug: str,
    reason: str = "done",
    agent: str = "lucy",
    ts: Optional[datetime] = None,
) -> TopicEvent:
    return _event(
        KIND_TOPIC_ARCHIVED,
        TopicArchivedPayload(reason=reason),
        stream=slug,
        agent=agent,
        ts=ts,
    )


class _ConversationEvent:
    """Forward-compat stand-in for a future conversation event kind.

    The v1 schema pins ``TopicEvent.kind`` to the six ``topic_*`` kinds
    (schema Literal), so this duck-typed event exercises the index's
    stream-binding path without widening the schema; conversation kinds
    arrive with migration/FCP integration.
    """

    def __init__(self, event_id: str, stream: str, ts: Optional[datetime] = None) -> None:
        self.event_id = event_id
        self.kind = "user_message"
        self.stream = stream
        self.ts = ts or datetime.now(timezone.utc)


@pytest.fixture
def store(tmp_path: Path) -> JsonlEventStore:
    return JsonlEventStore(tmp_path)


@pytest.fixture
def index(store: JsonlEventStore) -> TopicIndex:
    return TopicIndex(store)


def _append(store: JsonlEventStore, event: TopicEvent) -> None:
    store.append_event(ACCOUNT, event.stream, event)


def _snapshot(index: TopicIndex) -> list:
    """Deterministic projection snapshot (sorted by slug, archived included)."""
    return [r.model_dump() for r in index.list_topics(ACCOUNT, include_archived=True)]


# ---------------------------------------------------------------------------
# Idempotent rebuild (DoD 1)
# ---------------------------------------------------------------------------


class TestRebuildIdempotent:
    def _log(self, store: JsonlEventStore) -> None:
        _append(store, _created("alpha", name="Alpha Topic"))
        _append(store, _link("alpha", ["e1", "e2"]))
        _append(store, _renamed("alpha", "Alpha Topic", "Alpha v2"))
        _append(store, _created("bravo", name="Bravo Topic", description="second"))
        _append(store, _link("bravo", ["e3"]))
        _append(store, _archived("alpha"))

    def _all_events(self, store: JsonlEventStore) -> List[TopicEvent]:
        events: List[TopicEvent] = []
        for stream in store.list_streams(ACCOUNT):
            events.extend(store.stream_events(ACCOUNT, stream))
        return events

    def test_empty_account_rebuild(self, index: TopicIndex) -> None:
        index.rebuild(ACCOUNT)
        assert index.list_topics(ACCOUNT) == []
        assert index.get_topic(ACCOUNT, "anything") is None
        assert index.topic_ids(ACCOUNT) == []

    def test_rebuild_twice_identical(self, store: JsonlEventStore, index: TopicIndex) -> None:
        self._log(store)
        index.rebuild(ACCOUNT)
        first = _snapshot(index)
        index.rebuild(ACCOUNT)
        assert _snapshot(index) == first

    def test_partial_apply_equals_full_rebuild(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        self._log(store)
        events = self._all_events(store)

        # Full rebuild from empty state.
        full = TopicIndex(store)
        full.rebuild(ACCOUNT)

        # Partial state: apply the log in two chunks (split mid-stream so the
        # partial index is genuinely half-built when the second half lands).
        partial = TopicIndex(store)
        mid = len(events) // 2
        for ev in events[:mid]:
            partial.apply_event(ACCOUNT, ev)
        for ev in events[mid:]:
            partial.apply_event(ACCOUNT, ev)

        assert _snapshot(partial) == _snapshot(full)

    def test_apply_every_event_equals_rebuild(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        self._log(store)
        events = self._all_events(store)
        full = TopicIndex(store)
        full.rebuild(ACCOUNT)
        incr = TopicIndex(store)
        for ev in events:
            incr.apply_event(ACCOUNT, ev)
        assert _snapshot(incr) == _snapshot(full)

    def test_apply_then_rebuild_is_log_faithful(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        # apply_event-only state is a live projection; rebuild() resets to the
        # log, which is the source of truth.
        index.apply_event(ACCOUNT, _created("ghost"))
        assert index.get_topic(ACCOUNT, "ghost") is not None
        index.rebuild(ACCOUNT)
        assert index.get_topic(ACCOUNT, "ghost") is None


# ---------------------------------------------------------------------------
# Lifecycle: create / rename (identity model)
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_create_builds_record(self, store: JsonlEventStore, index: TopicIndex) -> None:
        _append(store, _created("my-topic", name="My Topic", description="about things"))
        index.rebuild(ACCOUNT)
        rec = index.get_topic(ACCOUNT, "my-topic")
        assert rec is not None
        assert rec.topic_id == "my-topic"
        assert rec.name == "My Topic"
        assert rec.description == "about things"
        assert rec.kind == KIND_EXPLICIT
        assert rec.archived is False
        assert rec.event_ids == []

    def test_rename_keeps_slug(self, store: JsonlEventStore, index: TopicIndex) -> None:
        _append(store, _created("my-topic", name="My Topic"))
        _append(store, _renamed("my-topic", "My Topic", "My Topic v2"))
        index.rebuild(ACCOUNT)
        rec = index.get_topic(ACCOUNT, "my-topic")
        assert rec is not None
        assert rec.topic_id == "my-topic"  # slug immutable
        assert rec.name == "My Topic v2"
        assert index.topic_ids(ACCOUNT) == ["my-topic"]

    def test_created_and_updated_timestamps(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        t0 = datetime(2026, 9, 1, 8, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(minutes=5)
        _append(store, _created("my-topic", ts=t0))
        _append(store, _link("my-topic", ["e1"], ts=t1))
        index.rebuild(ACCOUNT)
        rec = index.get_topic(ACCOUNT, "my-topic")
        assert rec is not None
        assert rec.created_at == t0
        assert rec.updated_at == t1


# ---------------------------------------------------------------------------
# Re-tagging via link/unlink (DoD 2)
# ---------------------------------------------------------------------------


class TestReTagging:
    def test_link_adds_membership(self, store: JsonlEventStore, index: TopicIndex) -> None:
        _append(store, _created("notes"))
        _append(store, _link("notes", ["e1", "e2"]))
        index.rebuild(ACCOUNT)
        assert index.event_ids(ACCOUNT, "notes") == ["e1", "e2"]

    def test_unlink_removes_membership(self, store: JsonlEventStore, index: TopicIndex) -> None:
        _append(store, _created("notes"))
        _append(store, _link("notes", ["e1", "e2", "e3"]))
        _append(store, _unlink("notes", ["e1"]))
        index.rebuild(ACCOUNT)
        assert index.event_ids(ACCOUNT, "notes") == ["e2", "e3"]

    def test_re_tagging_never_moves_events(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        # An unattributed event lands in the inbox (default destination).
        _append(store, _link(INBOX_STREAM, ["e1"]))
        _append(store, _created("notes"))
        # Re-tag e1 into "notes": membership changes, the event stays put.
        _append(store, _link("notes", ["e1"]))
        index.rebuild(ACCOUNT)

        assert index.event_ids(ACCOUNT, "notes") == ["e1"]
        assert index.event_ids(ACCOUNT, INBOX_STREAM) == []  # inbox is not a topic

        inbox_file = store._data_root / inbox_path(ACCOUNT)
        assert "e1" in inbox_file.read_text(encoding="utf-8")  # event never moved

        notes_file = store._data_root / stream_path(ACCOUNT, "notes")
        lines = notes_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2  # topic_created + topic_link only; nothing copied

    def test_inbox_events_never_members(self, store: JsonlEventStore, index: TopicIndex) -> None:
        _append(store, _link(INBOX_STREAM, ["e1", "e2"]))
        _append(store, _created("other"))
        index.rebuild(ACCOUNT)
        # Nothing in the inbox is attributed to any topic until linked.
        assert index.event_ids(ACCOUNT, "other") == []
        assert index.topic_ids(ACCOUNT) == ["other"]


# ---------------------------------------------------------------------------
# Archive semantics (DoD 3)
# ---------------------------------------------------------------------------


class TestArchive:
    def test_archived_excluded_from_active_queries(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("active-topic"))
        _append(store, _created("done-topic"))
        _append(store, _archived("done-topic"))
        index.rebuild(ACCOUNT)

        assert index.topic_ids(ACCOUNT) == ["active-topic"]
        assert index.topic_ids(ACCOUNT, include_archived=True) == [
            "active-topic",
            "done-topic",
        ]
        records = index.list_topics(ACCOUNT)
        assert [r.topic_id for r in records] == ["active-topic"]

    def test_archived_still_queryable_by_id(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("done-topic"))
        _append(store, _link("done-topic", ["e1"]))
        _append(store, _archived("done-topic", reason="finished"))
        index.rebuild(ACCOUNT)
        rec = index.get_topic(ACCOUNT, "done-topic")
        assert rec is not None
        assert rec.archived is True
        assert rec.event_ids == ["e1"]  # existing events stay queryable
        assert index.is_archived(ACCOUNT, "done-topic") is True

    def test_archive_before_create_is_order_independent(self, index: TopicIndex) -> None:
        # Out-of-order incremental application: archived seen before the
        # topic_created (cross-stream replay order) must not create a phantom
        # topic, and the topic must come up archived.
        index.apply_event(ACCOUNT, _archived("old-topic"))
        assert index.get_topic(ACCOUNT, "old-topic") is None
        index.apply_event(ACCOUNT, _created("old-topic"))
        assert index.get_topic(ACCOUNT, "old-topic") is not None
        assert index.is_archived(ACCOUNT, "old-topic") is True
        assert index.topic_ids(ACCOUNT) == []  # archived: not active


# ---------------------------------------------------------------------------
# Merge semantics (DoD: merged topics re-link)
# ---------------------------------------------------------------------------


class TestMerge:
    def test_merge_relinks_and_freezes_source(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("alpha", name="Alpha"))
        _append(store, _link("alpha", ["e1", "e2"]))
        _append(store, _created("bravo", name="Bravo"))
        _append(store, _link("bravo", ["e3"]))

        # Merge alpha into bravo (the t-mutation event sequence):
        # topic_merged + topic_link(A's ids -> B) appended to B's stream,
        # topic_archived appended to A's stream.
        _append(store, _merged("alpha", "bravo"))
        _append(store, _link("bravo", ["e1", "e2"], reason="merge"))
        _append(store, _archived("alpha"))

        index.rebuild(ACCOUNT)

        target = index.get_topic(ACCOUNT, "bravo")
        assert target is not None
        assert target.event_ids == ["e1", "e2", "e3"]  # re-linked into the target

        source = index.get_topic(ACCOUNT, "alpha")
        assert source is not None
        assert source.archived is True  # frozen
        # The design's merge sequence has no unlink, so the source keeps its
        # derived ids (faithful replay) and stays queryable while archived.
        assert source.event_ids == ["e1", "e2"]

        assert index.topic_ids(ACCOUNT) == ["bravo"]  # source excluded from active

    def test_merge_before_create_is_order_independent(self, index: TopicIndex) -> None:
        # Cross-stream order: the merge event (in bravo's stream) is applied
        # before alpha's topic_created; alpha must still come up frozen.
        index.apply_event(ACCOUNT, _merged("alpha", "bravo"))
        index.apply_event(ACCOUNT, _created("bravo"))
        index.apply_event(ACCOUNT, _created("alpha"))
        assert index.is_archived(ACCOUNT, "alpha") is True
        assert index.is_archived(ACCOUNT, "bravo") is False


# ---------------------------------------------------------------------------
# Topics by kind
# ---------------------------------------------------------------------------


class TestTopicsByKind:
    def test_explicit_kind_partition(self, store: JsonlEventStore, index: TopicIndex) -> None:
        _append(store, _created("one"))
        _append(store, _created("two"))
        _append(store, _archived("two"))
        index.rebuild(ACCOUNT)
        assert [r.topic_id for r in index.topics_by_kind(ACCOUNT, KIND_EXPLICIT)] == ["one"]
        assert [r.topic_id for r in index.topics_by_kind(ACCOUNT, KIND_EXPLICIT, include_archived=True)] == [
            "one",
            "two",
        ]

    def test_future_kinds_empty(self, index: TopicIndex) -> None:
        # v1: explicit topics only (decisions 5, 8).
        assert index.topics_by_kind(ACCOUNT, KIND_TEMPORAL) == []
        assert index.topics_by_kind(ACCOUNT, KIND_INFERRED) == []


# ---------------------------------------------------------------------------
# Stream binding (forward-compatible, decision 1)
# ---------------------------------------------------------------------------


class TestStreamBinding:
    def test_non_topic_event_binds_to_topic_stream(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("my-topic"))
        index.rebuild(ACCOUNT)
        # A future conversation event appended to the topic's own stream is a
        # member (placement = membership in the common case).
        index.apply_event(ACCOUNT, _ConversationEvent("ev-1", "my-topic"))
        assert index.event_ids(ACCOUNT, "my-topic") == ["ev-1"]
        # The index is a projection: rebuild drops events not in the log.
        index.rebuild(ACCOUNT)
        assert index.event_ids(ACCOUNT, "my-topic") == []

    def test_inbox_conversation_event_never_binds(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("my-topic"))
        index.rebuild(ACCOUNT)
        index.apply_event(ACCOUNT, _ConversationEvent("ev-inbox", INBOX_STREAM))
        assert index.event_ids(ACCOUNT, "my-topic") == []

    def test_binding_before_create_is_buffered(self, index: TopicIndex) -> None:
        # Events seen before their topic_created are buffered and absorbed at
        # creation, so incremental application is order-independent.
        index.apply_event(ACCOUNT, _ConversationEvent("ev-1", "my-topic"))
        index.apply_event(ACCOUNT, _created("my-topic"))
        assert index.event_ids(ACCOUNT, "my-topic") == ["ev-1"]


# ---------------------------------------------------------------------------
# The inbox is never a topic
# ---------------------------------------------------------------------------


class TestInboxNeverTopic:
    def test_misplaced_topic_created_in_inbox_ignored(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        # A topic_created whose slug collides with the inbox stream name is a
        # stream-name collision the mutation layer must reserve against; the
        # index is defensive and never turns the inbox into a topic.
        ev = TopicEvent(
            kind=KIND_TOPIC_CREATED,
            agent="lucy",
            account=ACCOUNT,
            stream=INBOX_STREAM,
            payload=TopicCreatedPayload(name="Inbox", slug=INBOX_STREAM),
        )
        _append(store, ev)
        index.rebuild(ACCOUNT)
        assert index.get_topic(ACCOUNT, INBOX_STREAM) is None
        assert index.topic_ids(ACCOUNT) == []

    def test_link_targeting_inbox_changes_nothing(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("notes"))
        _append(store, _link(INBOX_STREAM, ["e1"]))
        index.rebuild(ACCOUNT)
        assert index.event_ids(ACCOUNT, "notes") == []
        assert index.topic_ids(ACCOUNT) == ["notes"]


# ---------------------------------------------------------------------------
# No agent partitioning at the index level (decision 7)
# ---------------------------------------------------------------------------


class TestNoAgentPartitioning:
    def test_membership_independent_of_agent(
        self, store: JsonlEventStore, index: TopicIndex
    ) -> None:
        _append(store, _created("shared-topic", agent="lucy"))
        _append(store, _link("shared-topic", ["e1"], agent="lucy"))
        _append(store, _link("shared-topic", ["e2"], agent="ziggy"))
        _append(store, _unlink("shared-topic", ["e1"], agent="ziggy"))
        index.rebuild(ACCOUNT)
        # Both agents' events land in the same topic; membership never depends
        # on which agent wrote the event.
        assert index.event_ids(ACCOUNT, "shared-topic") == ["e2"]


# ---------------------------------------------------------------------------
# Seam
# ---------------------------------------------------------------------------


class TestSeam:
    def test_index_consumes_eventstore_abc(self, store: JsonlEventStore) -> None:
        assert isinstance(store, EventStore)
        index = TopicIndex(store)
        assert isinstance(index, TopicIndex)
