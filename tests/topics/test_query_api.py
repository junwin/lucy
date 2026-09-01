"""
Tests for src/topics/queries.py - the topic query API (issue #129).

Covers the t-query-api DoD:
- topic by topic_id returns the topic record incl. derived event_ids
- events in topic are newest-first and the limit is honored
- topics by kind returns the correct partition (explicit vs archived)
- event-date filter works with inclusive range
- pytest tests/topics/test_query_api.py -q green

Also covers the composed ``TopicStoreImpl`` (mutations immediately visible to
queries, shared index) and the guardrails: no semantic search (decision 3),
agent never a partition key (decision 7), no topic_id on events (decision 1).

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import pytest

from src.storage.interfaces import EventStore, TopicStore
from src.topics.index import TopicIndex
from src.topics.mutation import TopicMutations
from src.topics.queries import TopicQueries, TopicStoreImpl
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    TopicEvent,
    TopicLinkPayload,
)
from src.topics.streams import JsonlEventStore

ACCOUNT = "junwin"

T0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> JsonlEventStore:
    return JsonlEventStore(tmp_path)


@pytest.fixture
def index(store: JsonlEventStore) -> TopicIndex:
    return TopicIndex(store)


@pytest.fixture
def queries(store: JsonlEventStore, index: TopicIndex) -> TopicQueries:
    return TopicQueries(store, index)


@pytest.fixture
def impl(store: JsonlEventStore) -> TopicStoreImpl:
    return TopicStoreImpl(store)


def _seed_inbox_event(
    store: JsonlEventStore,
    event_id: str,
    *,
    ts: datetime | None = None,
    agent: str = "lucy",
) -> TopicEvent:
    """Create a resolvable member-able event in the inbox (v1 placeholder).

    v1 schemas only define the six ``topic_*`` kinds, so a stand-in event is
    appended to the inbox: a ``topic_link`` targeting the inbox is legal,
    never becomes a topic (index ignores it), and is resolvable by id from
    the account's streams - the same resolution path any future conversation
    kind will take (stream binding / migration events).
    """
    return store.append_event(
        ACCOUNT,
        INBOX_STREAM,
        TopicEvent(
            event_id=event_id,
            kind=KIND_TOPIC_LINK,
            agent=agent,
            account=ACCOUNT,
            stream=INBOX_STREAM,
            ts=ts if ts is not None else T0,
            payload=TopicLinkPayload(topic=INBOX_STREAM, event_ids=[f"{event_id}-ref"]),
        ),
    )


def _ids(events: List[TopicEvent]) -> List[str]:
    return [e.event_id for e in events]


def _make_topic_with_events(store: JsonlEventStore, queries: TopicQueries) -> str:
    """notes topic with three linked events at T0, T0+1m, T0+2m (ascending)."""
    slug = "notes"
    impl = TopicStoreImpl(store)
    impl.create_topic(ACCOUNT, "Notes", slug, agent="lucy")
    for i, ts in enumerate([T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=2)]):
        _seed_inbox_event(store, f"e{i + 1}", ts=ts)
    impl.link_events(ACCOUNT, slug, ["e1", "e2", "e3"], agent="lucy")
    queries.rebuild(ACCOUNT)  # see the seeds written directly to the store
    return slug


# ---------------------------------------------------------------------------
# DoD 1: topic by topic_id returns the record incl. derived event_ids
# ---------------------------------------------------------------------------


class TestGetTopic:
    def test_returns_record_with_derived_event_ids(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        _make_topic_with_events(store, queries)
        rec = queries.get_topic(ACCOUNT, "notes")
        assert rec is not None
        assert rec.topic_id == "notes"  # slug = topic_id (identity model)
        assert rec.kind == "explicit"
        assert rec.name == "Notes"
        assert rec.event_ids == ["e1", "e2", "e3"]  # derived membership
        assert rec.archived is False
        assert rec.created_at is not None

    def test_unknown_topic_returns_none(self, queries: TopicQueries) -> None:
        assert queries.get_topic(ACCOUNT, "ghost") is None

    def test_archived_topic_still_queryable(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        impl = TopicStoreImpl(store)
        impl.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0)
        impl.link_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")
        impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        rec = queries.get_topic(ACCOUNT, "done-topic")
        assert rec is not None
        assert rec.archived is True
        assert rec.event_ids == ["e1"]  # existing events stay queryable

    def test_lifecycle_events_are_not_members(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        # A freshly created topic with no links has no member events - the
        # topic_created lifecycle event is not a member (decision 1).
        impl = TopicStoreImpl(store)
        impl.create_topic(ACCOUNT, "Empty", "empty-topic", agent="lucy")
        assert queries.get_topic(ACCOUNT, "empty-topic") is not None
        assert queries.event_ids(ACCOUNT, "empty-topic") == []


# ---------------------------------------------------------------------------
# DoD 2: events in topic are newest-first and the limit is honored
# ---------------------------------------------------------------------------


class TestEventsInTopic:
    def test_newest_first(self, store: JsonlEventStore, queries: TopicQueries) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(ACCOUNT, "notes")
        assert _ids(events) == ["e3", "e2", "e1"]  # newest first

    def test_limit_honored(self, store: JsonlEventStore, queries: TopicQueries) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(ACCOUNT, "notes", limit=2)
        assert _ids(events) == ["e3", "e2"]
        assert queries.events_in_topic(ACCOUNT, "notes", limit=1) == [events[0]]

    def test_limit_none_returns_all(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        _make_topic_with_events(store, queries)
        assert len(queries.events_in_topic(ACCOUNT, "notes")) == 3

    def test_unknown_topic_returns_empty(self, queries: TopicQueries) -> None:
        assert queries.events_in_topic(ACCOUNT, "ghost") == []

    def test_members_resolve_across_streams(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        # Members can be re-tagged from any stream: one event seeded in the
        # inbox, another in a different topic's stream, both linked into notes.
        impl = TopicStoreImpl(store)
        impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        impl.create_topic(ACCOUNT, "Other", "other", agent="lucy")
        _seed_inbox_event(store, "e-inbox", ts=T0)
        store.append_event(
            ACCOUNT,
            "other",
            TopicEvent(
                event_id="e-other",
                kind=KIND_TOPIC_LINK,
                agent="ziggy",
                account=ACCOUNT,
                stream="other",
                ts=T0 + timedelta(minutes=1),
                payload=TopicLinkPayload(topic="other", event_ids=["e-other-ref"]),
            ),
        )
        # Separate index instances: rebuild the queries fixture after the
        # impl's link so it derives membership from the log (source of truth).
        impl.link_events(ACCOUNT, "notes", ["e-inbox", "e-other"], agent="lucy")
        queries.rebuild(ACCOUNT)
        events = queries.events_in_topic(ACCOUNT, "notes")
        assert _ids(events) == ["e-other", "e-inbox"]  # newest first

    def test_archived_topic_events_still_queryable(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        impl = TopicStoreImpl(store)
        impl.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0)
        impl.link_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")
        impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        events = queries.events_in_topic(ACCOUNT, "done-topic")
        assert _ids(events) == ["e1"]  # archive = freeze, not delete

    def test_dangling_ids_are_skipped(self, queries: TopicQueries) -> None:
        # Linked ids that do not resolve to any event in the log are skipped
        # (the log is the source of truth), not fatal.
        impl_store = queries._store
        impl = TopicStoreImpl(impl_store)
        impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        impl.link_events(ACCOUNT, "notes", ["never-appended"], agent="lucy")
        assert queries.events_in_topic(ACCOUNT, "notes") == []
        assert queries.event_ids(ACCOUNT, "notes") == ["never-appended"]


# ---------------------------------------------------------------------------
# DoD 3: topics by kind returns the correct partition (explicit vs archived)
# ---------------------------------------------------------------------------


class TestTopicsByKind:
    def _two_topics(self, store: JsonlEventStore) -> TopicStoreImpl:
        impl = TopicStoreImpl(store)
        impl.create_topic(ACCOUNT, "Active", "active-topic", agent="lucy")
        impl.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        impl.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        return impl

    def test_explicit_partition_excludes_archived(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        self._two_topics(store)
        recs = queries.topics_by_kind(ACCOUNT, "explicit")
        assert [r.topic_id for r in recs] == ["active-topic"]

    def test_explicit_partition_with_archived(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        self._two_topics(store)
        recs = queries.topics_by_kind(ACCOUNT, "explicit", include_archived=True)
        assert [r.topic_id for r in recs] == ["active-topic", "done-topic"]
        assert {r.archived for r in recs} == {False, True}

    def test_future_kinds_empty_in_v1(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        self._two_topics(store)
        # Temporal/inferred topics are deferred (decisions 5, 10; Phase 2).
        assert queries.topics_by_kind(ACCOUNT, "temporal") == []
        assert queries.topics_by_kind(ACCOUNT, "inferred") == []

    def test_list_topics_kind_filter_abc_signature(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        self._two_topics(store)
        assert [r.topic_id for r in queries.list_topics(ACCOUNT, kind="explicit")] == [
            "active-topic"
        ]

    def test_list_topics_default_active_only(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        self._two_topics(store)
        assert [r.topic_id for r in queries.list_topics(ACCOUNT)] == ["active-topic"]

    def test_empty_account(self, queries: TopicQueries) -> None:
        assert queries.list_topics(ACCOUNT) == []
        assert queries.topics_by_kind(ACCOUNT, "explicit") == []


# ---------------------------------------------------------------------------
# DoD 4: event-date filter works with inclusive range
# ---------------------------------------------------------------------------


class TestDateFilter:
    def test_inclusive_start(self, store: JsonlEventStore, queries: TopicQueries) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(ACCOUNT, "notes", start_ts=T0 + timedelta(minutes=1))
        assert _ids(events) == ["e3", "e2"]  # boundary event included

    def test_inclusive_end(self, store: JsonlEventStore, queries: TopicQueries) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(ACCOUNT, "notes", end_ts=T0 + timedelta(minutes=1))
        assert _ids(events) == ["e2", "e1"]  # boundary event included

    def test_inclusive_range(self, store: JsonlEventStore, queries: TopicQueries) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(
            ACCOUNT,
            "notes",
            start_ts=T0 + timedelta(minutes=1),
            end_ts=T0 + timedelta(minutes=1),
        )
        assert _ids(events) == ["e2"]  # single event, inclusive both ends

    def test_full_range_returns_all(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(
            ACCOUNT,
            "notes",
            start_ts=T0 - timedelta(hours=1),
            end_ts=T0 + timedelta(hours=1),
        )
        assert _ids(events) == ["e3", "e2", "e1"]

    def test_no_match_returns_empty(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        _make_topic_with_events(store, queries)
        assert (
            queries.events_in_topic(
                ACCOUNT, "notes", start_ts=T0 + timedelta(days=1)
            )
            == []
        )

    def test_naive_datetime_assumed_utc(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        _make_topic_with_events(store, queries)
        # Naive bound == same instant as the aware T0 (envelope normalizes to UTC).
        events = queries.events_in_topic(
            ACCOUNT,
            "notes",
            start_ts=datetime(2026, 9, 1, 10, 0, 0),
        )
        assert _ids(events) == ["e3", "e2", "e1"]

    def test_filter_combines_with_limit(
        self, store: JsonlEventStore, queries: TopicQueries
    ) -> None:
        _make_topic_with_events(store, queries)
        events = queries.events_in_topic(
            ACCOUNT, "notes", start_ts=T0, limit=2
        )
        assert _ids(events) == ["e3", "e2"]  # filter first, then cap


# ---------------------------------------------------------------------------
# Composed store: mutations immediately visible to queries (shared index)
# ---------------------------------------------------------------------------


class TestTopicStoreImpl:
    def test_implements_topicstore_abc(self, impl: TopicStoreImpl) -> None:
        assert isinstance(impl, TopicStore)
        assert isinstance(impl, TopicStoreImpl)

    def test_create_visible_in_queries(self, impl: TopicStoreImpl) -> None:
        slug = impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        rec = impl.get_topic(ACCOUNT, slug)
        assert rec is not None
        assert rec.topic_id == "notes"
        assert rec.name == "Notes"
        assert impl.topic_ids(ACCOUNT) == ["notes"]

    def test_link_then_events_in_topic(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0)
        _seed_inbox_event(store, "e2", ts=T0 + timedelta(minutes=1))
        impl.link_events(ACCOUNT, "notes", ["e1", "e2"], agent="lucy")
        # The event cache is refreshed after each mutation: no manual rebuild.
        assert _ids(impl.events_in_topic(ACCOUNT, "notes")) == ["e2", "e1"]

    def test_unlink_reflected_in_events(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0)
        _seed_inbox_event(store, "e2", ts=T0 + timedelta(minutes=1))
        impl.link_events(ACCOUNT, "notes", ["e1", "e2"], agent="lucy")
        impl.unlink_events(ACCOUNT, "notes", ["e1"], agent="lucy")
        assert _ids(impl.events_in_topic(ACCOUNT, "notes")) == ["e2"]

    def test_merge_relinks_into_target(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        impl.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        impl.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0)
        _seed_inbox_event(store, "e2", ts=T0 + timedelta(minutes=1))
        impl.link_events(ACCOUNT, "alpha", ["e1"], agent="lucy")
        impl.link_events(ACCOUNT, "bravo", ["e2"], agent="lucy")
        impl.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        assert _ids(impl.events_in_topic(ACCOUNT, "bravo")) == ["e2", "e1"]
        assert impl.is_archived(ACCOUNT, "alpha") is True
        assert impl.topic_ids(ACCOUNT) == ["bravo"]  # alpha not active

    def test_rebuild_sees_external_writes(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        # A direct store write bypassing the mutation layer:
        _seed_inbox_event(store, "e1", ts=T0)
        # The cache was refreshed before the direct write; rebuild restores truth.
        assert impl.events_in_topic(ACCOUNT, "notes") == []
        impl.rebuild(ACCOUNT)
        assert impl.event_ids(ACCOUNT, "notes") == []
        impl.link_events(ACCOUNT, "notes", ["e1"], agent="lucy")
        assert _ids(impl.events_in_topic(ACCOUNT, "notes")) == ["e1"]


# ---------------------------------------------------------------------------
# Validation / error handling
# ---------------------------------------------------------------------------


class TestValidation:
    def test_limit_must_be_positive_int(self, queries: TopicQueries) -> None:
        with pytest.raises(ValueError, match="limit"):
            queries.events_in_topic(ACCOUNT, "notes", limit=0)
        with pytest.raises(ValueError, match="limit"):
            queries.events_in_topic(ACCOUNT, "notes", limit=-1)
        with pytest.raises(ValueError, match="limit"):
            queries.events_in_topic(ACCOUNT, "notes", limit="5")


# ---------------------------------------------------------------------------
# Guardrails (decisions 1, 3, 7, 9)
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_no_semantic_search(self, queries: TopicQueries) -> None:
        # Decision 3: no topic embeddings in v1; discovery goes through digest
        # embeddings, so the query API is membership + date based only.
        import src.topics.queries as qmod

        src = qmod.__dict__
        assert not any("embed" in name.lower() for name in src)
        assert not any("vector" in name.lower() for name in src)

    def test_agent_never_a_partition_key(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        # Two agents' events land in one shared topic and both are returned.
        impl.create_topic(ACCOUNT, "Shared", "shared-topic", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0, agent="lucy")
        _seed_inbox_event(store, "e2", ts=T0 + timedelta(minutes=1), agent="ziggy")
        impl.link_events(ACCOUNT, "shared-topic", ["e1", "e2"], agent="lucy")
        events = impl.events_in_topic(ACCOUNT, "shared-topic")
        assert {e.agent for e in events} == {"lucy", "ziggy"}
        assert _ids(events) == ["e2", "e1"]

    def test_events_never_carry_topic_id(
        self, store: JsonlEventStore, impl: TopicStoreImpl
    ) -> None:
        impl.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        _seed_inbox_event(store, "e1", ts=T0)
        impl.link_events(ACCOUNT, "notes", ["e1"], agent="lucy")
        for stream in store.list_streams(ACCOUNT):
            for line in (store._data_root / f"topics/{ACCOUNT}/{stream}.jsonl").read_text(
                encoding="utf-8"
            ).splitlines():
                assert '"topic_id"' not in line  # decision 1

    def test_queries_consume_eventstore_abc(self, store: JsonlEventStore) -> None:
        assert isinstance(store, EventStore)
        q = TopicQueries(store)
        assert isinstance(q, TopicQueries)
        m = TopicMutations(store)
        assert isinstance(m, TopicMutations)
