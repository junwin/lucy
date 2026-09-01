"""
Tests for src/topics/mutation.py - the topic mutation API (issue #129).

Covers the t-mutation-api DoD:
- each operation appends at least one event and never modifies existing events
- merge freezes the source topic and re-links all of its event ids to the
  target
- archive freezes the stream; rename never changes the slug
- creating with a colliding slug returns a deterministic suffixed slug
  (-2, -3, ...)
- pytest tests/topics/test_mutation_api.py -q green

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pytest

from src.storage.interfaces import EventStore
from src.topics.index import TopicIndex
from src.topics.mutation import (
    TopicArchivedError,
    TopicError,
    TopicMutations,
    TopicNotFoundError,
)
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    KIND_TOPIC_MERGED,
    KIND_TOPIC_RENAMED,
    KIND_TOPIC_UNLINK,
    TopicCreatedPayload,
    TopicEvent,
    TopicLinkPayload,
    inbox_path,
    stream_path,
)
from src.topics.streams import JsonlEventStore, StreamArchivedError

ACCOUNT = "junwin"


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
def topics(store: JsonlEventStore, index: TopicIndex) -> TopicMutations:
    return TopicMutations(store, index)


def _raw_lines(store: JsonlEventStore, stream: str) -> List[str]:
    """Raw JSONL lines of a stream file (the bytes as appended)."""
    path = store._data_root / stream_path(ACCOUNT, stream)
    assert path.exists(), f"stream file missing: {path}"
    return path.read_text(encoding="utf-8").splitlines()


def _kinds(store: JsonlEventStore, stream: str) -> List[str]:
    return [
        TopicEvent.model_validate_json(line).kind for line in _raw_lines(store, stream)
    ]


def _link_event(slug: str, event_ids: List[str]) -> TopicEvent:
    return TopicEvent(
        kind=KIND_TOPIC_LINK,
        agent="lucy",
        account=ACCOUNT,
        stream=slug,
        payload=TopicLinkPayload(topic=slug, event_ids=event_ids),
    )


# ---------------------------------------------------------------------------
# DoD 1: every operation appends >= 1 event; never modifies existing events
# ---------------------------------------------------------------------------


class TestAppendOnly:
    def test_create_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None:
        slug = topics.create_topic(ACCOUNT, "My Topic", "my-topic", agent="lucy")
        assert slug == "my-topic"
        lines = _raw_lines(store, "my-topic")
        assert len(lines) == 1
        ev = TopicEvent.model_validate_json(lines[0])
        assert ev.kind == KIND_TOPIC_CREATED
        assert ev.payload.name == "My Topic"
        assert ev.payload.slug == "my-topic"
        assert ev.agent == "lucy"
        assert ev.account == ACCOUNT
        assert ev.stream == "my-topic"

    def test_rename_appends_without_touching_prior_lines(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        before = _raw_lines(store, "alpha")
        topics.rename_topic(ACCOUNT, "alpha", "Alpha v2", agent="lucy")
        lines = _raw_lines(store, "alpha")
        assert len(lines) == 2
        assert lines[0] == before[0]  # original line byte-identical
        ev = TopicEvent.model_validate_json(lines[1])
        assert ev.kind == KIND_TOPIC_RENAMED
        assert ev.payload.old_name == "Alpha"
        assert ev.payload.new_name == "Alpha v2"

    def test_link_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        topics.link_events(ACCOUNT, "notes", ["e1", "e2"], agent="ziggy")
        lines = _raw_lines(store, "notes")
        assert len(lines) == 2
        ev = TopicEvent.model_validate_json(lines[1])
        assert ev.kind == KIND_TOPIC_LINK
        assert ev.payload.topic == "notes"
        assert ev.payload.event_ids == ["e1", "e2"]
        assert ev.agent == "ziggy"  # agent is metadata on the event

    def test_unlink_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        topics.link_events(ACCOUNT, "notes", ["e1", "e2"], agent="lucy")
        topics.unlink_events(ACCOUNT, "notes", ["e1"], agent="ziggy")
        lines = _raw_lines(store, "notes")
        assert len(lines) == 3
        ev = TopicEvent.model_validate_json(lines[2])
        assert ev.kind == KIND_TOPIC_UNLINK
        assert ev.payload.event_ids == ["e1"]
        assert topics.index.event_ids(ACCOUNT, "notes") == ["e2"]

    def test_merge_appends_three_events(self, store: JsonlEventStore, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        topics.link_events(ACCOUNT, "alpha", ["e1", "e2"], agent="lucy")
        topics.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        topics.link_events(ACCOUNT, "bravo", ["e3"], agent="lucy")
        topics.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        # target stream: created + link(e3) + merged + link(e1,e2)
        assert _kinds(store, "bravo") == [
            KIND_TOPIC_CREATED,
            KIND_TOPIC_LINK,
            KIND_TOPIC_MERGED,
            KIND_TOPIC_LINK,
        ]
        # source stream: created + link(e1,e2) + archived (frozen)
        assert _kinds(store, "alpha") == [
            KIND_TOPIC_CREATED,
            KIND_TOPIC_LINK,
            KIND_TOPIC_ARCHIVED,
        ]

    def test_archive_appends_one_event(self, store: JsonlEventStore, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy", reason="finished")
        lines = _raw_lines(store, "done-topic")
        assert len(lines) == 2
        ev = TopicEvent.model_validate_json(lines[1])
        assert ev.kind == KIND_TOPIC_ARCHIVED
        assert ev.payload.reason == "finished"

    def test_full_sequence_never_rewrites_earlier_lines(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        first = _raw_lines(store, "notes")[0]
        topics.rename_topic(ACCOUNT, "notes", "Notes v2", agent="lucy")
        topics.link_events(ACCOUNT, "notes", ["e1"], agent="ziggy")
        topics.unlink_events(ACCOUNT, "notes", ["e1"], agent="ziggy")
        topics.archive_topic(ACCOUNT, "notes", agent="lucy")
        lines = _raw_lines(store, "notes")
        assert len(lines) == 5
        assert lines[0] == first  # the topic_created line is untouched


# ---------------------------------------------------------------------------
# DoD 2: merge freezes the source and re-links all of its ids to the target
# ---------------------------------------------------------------------------


class TestMerge:
    def _pair(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        topics.link_events(ACCOUNT, "alpha", ["e1", "e2"], agent="lucy")
        topics.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        topics.link_events(ACCOUNT, "bravo", ["e3"], agent="lucy")

    def test_merge_relinks_all_source_ids(self, topics: TopicMutations) -> None:
        self._pair(topics)
        topics.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        target = topics.index.get_topic(ACCOUNT, "bravo")
        assert target is not None
        assert target.event_ids == ["e1", "e2", "e3"]  # re-linked into the target
        source = topics.index.get_topic(ACCOUNT, "alpha")
        assert source is not None
        assert source.archived is True  # frozen
        # The design's merge sequence has no unlink: the source keeps its
        # derived ids (faithful replay) and stays queryable while archived.
        assert source.event_ids == ["e1", "e2"]
        assert topics.index.topic_ids(ACCOUNT) == ["bravo"]  # source not active

    def test_merge_freezes_source_stream(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        self._pair(topics)
        topics.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        # The store rejects direct writes to the frozen source stream...
        with pytest.raises(StreamArchivedError):
            store.append_event(ACCOUNT, "alpha", _link_event("alpha", ["e9"]))
        # ...and the mutation layer refuses further operations on the source.
        with pytest.raises(TopicArchivedError):
            topics.link_events(ACCOUNT, "alpha", ["e9"], agent="lucy")

    def test_merge_into_archived_target_rejected(self, topics: TopicMutations) -> None:
        self._pair(topics)
        topics.archive_topic(ACCOUNT, "bravo", agent="lucy")
        with pytest.raises(TopicArchivedError):
            topics.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")

    def test_merge_archived_source_rejected(self, topics: TopicMutations) -> None:
        self._pair(topics)
        topics.archive_topic(ACCOUNT, "alpha", agent="lucy")
        with pytest.raises(TopicArchivedError):
            topics.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")

    def test_merge_into_self_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        with pytest.raises(ValueError, match="differ"):
            topics.merge_topics(ACCOUNT, "alpha", "alpha", agent="lucy")

    def test_merge_unknown_topics_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        with pytest.raises(TopicNotFoundError):
            topics.merge_topics(ACCOUNT, "ghost", "bravo", agent="lucy")
        with pytest.raises(TopicNotFoundError):
            topics.merge_topics(ACCOUNT, "bravo", "ghost", agent="lucy")

    def test_merge_empty_source_skips_link_event(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        # A source with no derived ids: merged + archived only (the schema
        # requires topic_link to carry at least one event id).
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        topics.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        topics.merge_topics(ACCOUNT, "alpha", "bravo", agent="lucy")
        assert _kinds(store, "bravo") == [KIND_TOPIC_CREATED, KIND_TOPIC_MERGED]
        assert _kinds(store, "alpha") == [KIND_TOPIC_CREATED, KIND_TOPIC_ARCHIVED]
        assert topics.index.event_ids(ACCOUNT, "bravo") == []


# ---------------------------------------------------------------------------
# DoD 3: archive freezes the stream; rename never changes the slug
# ---------------------------------------------------------------------------


class TestArchiveAndRename:
    def test_archive_freezes_stream(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        assert store.is_archived(ACCOUNT, "done-topic") is True
        with pytest.raises(StreamArchivedError):
            store.append_event(ACCOUNT, "done-topic", _link_event("done-topic", ["e9"]))

    def test_archive_keeps_events_queryable(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.link_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        rec = topics.index.get_topic(ACCOUNT, "done-topic")
        assert rec is not None
        assert rec.archived is True
        assert rec.event_ids == ["e1"]  # existing events stay queryable
        assert topics.index.topic_ids(ACCOUNT) == []  # not active

    def test_archive_twice_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        with pytest.raises(TopicArchivedError):
            topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")

    def test_archive_unknown_topic_rejected(self, topics: TopicMutations) -> None:
        with pytest.raises(TopicNotFoundError):
            topics.archive_topic(ACCOUNT, "ghost", agent="lucy")

    def test_rename_keeps_slug(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "My Topic", "my-topic", agent="lucy")
        topics.rename_topic(ACCOUNT, "my-topic", "My Topic v2", agent="lucy")
        rec = topics.index.get_topic(ACCOUNT, "my-topic")
        assert rec is not None
        assert rec.topic_id == "my-topic"  # slug immutable
        assert rec.name == "My Topic v2"
        assert topics.index.topic_ids(ACCOUNT) == ["my-topic"]

    def test_rename_unknown_topic_rejected(self, topics: TopicMutations) -> None:
        with pytest.raises(TopicNotFoundError):
            topics.rename_topic(ACCOUNT, "ghost", "New", agent="lucy")

    def test_rename_archived_topic_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        with pytest.raises(TopicArchivedError):
            topics.rename_topic(ACCOUNT, "done-topic", "Renamed", agent="lucy")


# ---------------------------------------------------------------------------
# DoD 4: colliding slug -> deterministic suffix (-2, -3, ...)
# ---------------------------------------------------------------------------


class TestSlugResolution:
    def test_collision_gets_deterministic_suffix(self, topics: TopicMutations) -> None:
        assert topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy") == "alpha"
        assert topics.create_topic(ACCOUNT, "Alpha 2", "alpha", agent="lucy") == "alpha-2"
        assert topics.create_topic(ACCOUNT, "Alpha 3", "alpha", agent="lucy") == "alpha-3"

    def test_collision_after_normalization(self, topics: TopicMutations) -> None:
        assert (
            topics.create_topic(ACCOUNT, "A", "Alpha Topic!", agent="lucy")
            == "alpha-topic"
        )
        assert (
            topics.create_topic(ACCOUNT, "B", "Alpha Topic", agent="lucy")
            == "alpha-topic-2"
        )
        assert (
            topics.create_topic(ACCOUNT, "C", "alpha  topic", agent="lucy")
            == "alpha-topic-3"
        )

    def test_inbox_slug_is_reserved(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        slug = topics.create_topic(ACCOUNT, "Inbox", "inbox", agent="lucy")
        assert slug == "inbox-2"  # never the inbox stream name
        assert store.stream_exists(ACCOUNT, "inbox-2")
        assert not (store._data_root / inbox_path(ACCOUNT)).exists()
        assert topics.index.get_topic(ACCOUNT, "inbox-2") is not None
        assert topics.index.get_topic(ACCOUNT, "inbox") is None

    def test_invalid_proposal_rejected(self, topics: TopicMutations) -> None:
        with pytest.raises(ValueError):
            topics.create_topic(ACCOUNT, "Bad", "!!!", agent="lucy")
        with pytest.raises(ValueError):
            topics.create_topic(ACCOUNT, "Empty", "", agent="lucy")


# ---------------------------------------------------------------------------
# Link / unlink semantics
# ---------------------------------------------------------------------------


class TestLinkUnlink:
    def test_link_then_unlink_updates_membership(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        topics.link_events(ACCOUNT, "notes", ["e1", "e2"], agent="lucy")
        assert topics.index.event_ids(ACCOUNT, "notes") == ["e1", "e2"]
        topics.unlink_events(ACCOUNT, "notes", ["e2"], agent="ziggy")
        assert topics.index.event_ids(ACCOUNT, "notes") == ["e1"]

    def test_link_unknown_topic_rejected(self, topics: TopicMutations) -> None:
        with pytest.raises(TopicNotFoundError):
            topics.link_events(ACCOUNT, "ghost", ["e1"], agent="lucy")

    def test_unlink_unknown_topic_rejected(self, topics: TopicMutations) -> None:
        with pytest.raises(TopicNotFoundError):
            topics.unlink_events(ACCOUNT, "ghost", ["e1"], agent="lucy")

    def test_link_archived_topic_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        with pytest.raises(TopicArchivedError):
            topics.link_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")

    def test_unlink_archived_topic_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Done", "done-topic", agent="lucy")
        topics.archive_topic(ACCOUNT, "done-topic", agent="lucy")
        with pytest.raises(TopicArchivedError):
            topics.unlink_events(ACCOUNT, "done-topic", ["e1"], agent="lucy")

    def test_empty_event_ids_rejected(self, topics: TopicMutations) -> None:
        topics.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        with pytest.raises(ValueError):
            topics.link_events(ACCOUNT, "notes", [], agent="lucy")
        with pytest.raises(ValueError):
            topics.unlink_events(ACCOUNT, "notes", [], agent="lucy")


# ---------------------------------------------------------------------------
# Agent is event metadata, never a partition key (decision 7)
# ---------------------------------------------------------------------------


class TestAgentMetadata:
    def test_agent_recorded_on_every_event(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Shared", "shared-topic", agent="lucy")
        topics.link_events(ACCOUNT, "shared-topic", ["e1"], agent="ziggy")
        agents = [
            TopicEvent.model_validate_json(line).agent
            for line in _raw_lines(store, "shared-topic")
        ]
        assert agents == ["lucy", "ziggy"]

    def test_two_agents_share_one_topic_stream(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Shared", "shared-topic", agent="lucy")
        topics.link_events(ACCOUNT, "shared-topic", ["e1"], agent="lucy")
        topics.link_events(ACCOUNT, "shared-topic", ["e2"], agent="ziggy")
        topics.unlink_events(ACCOUNT, "shared-topic", ["e1"], agent="ziggy")
        # One stream file for the topic, regardless of how many agents wrote.
        account_dir = store._data_root / Path(inbox_path(ACCOUNT)).parent
        files = [p.name for p in account_dir.iterdir() if p.is_file()]
        assert files == ["shared-topic.jsonl"]
        assert topics.index.event_ids(ACCOUNT, "shared-topic") == ["e2"]


# ---------------------------------------------------------------------------
# Index sync: mutations keep the derived index current
# ---------------------------------------------------------------------------


class TestIndexSync:
    def test_operations_reflect_in_index_without_rebuild(
        self, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        topics.link_events(ACCOUNT, "notes", ["e1"], agent="lucy")
        assert topics.index.get_topic(ACCOUNT, "notes") is not None
        assert topics.index.event_ids(ACCOUNT, "notes") == ["e1"]

    def test_fresh_instance_rebuilds_from_log(self, tmp_path: Path) -> None:
        store1 = JsonlEventStore(tmp_path)
        m1 = TopicMutations(store1)
        m1.create_topic(ACCOUNT, "Notes", "notes", agent="lucy")
        m1.link_events(ACCOUNT, "notes", ["e1"], agent="lucy")

        store2 = JsonlEventStore(tmp_path)
        m2 = TopicMutations(store2)
        # The first mutation op syncs the account's index from the log;
        # state is derived from the log, not from m1's memory.
        m2.rename_topic(ACCOUNT, "notes", "Notes v2", agent="ziggy")
        assert m2.index.event_ids(ACCOUNT, "notes") == ["e1"]
        assert m2.index.get_topic(ACCOUNT, "notes").name == "Notes v2"

    def test_rebuild_sees_external_writes(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        # An event appended directly to the store (bypassing the mutation
        # layer) is visible after rebuild: the log is the source of truth.
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        direct = TopicEvent(
            kind=KIND_TOPIC_CREATED,
            agent="lucy",
            account=ACCOUNT,
            stream="bravo",
            payload=TopicCreatedPayload(name="Bravo", slug="bravo"),
        )
        store.append_event(ACCOUNT, "bravo", direct)
        topics.rebuild(ACCOUNT)
        assert topics.index.get_topic(ACCOUNT, "bravo") is not None
        # The resolver now treats bravo as taken.
        assert topics.create_topic(ACCOUNT, "Bravo 2", "bravo", agent="lucy") == "bravo-2"


# ---------------------------------------------------------------------------
# Guardrails (decisions 1, 9)
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_events_never_carry_topic_id(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(ACCOUNT, "Alpha", "alpha", agent="lucy")
        topics.create_topic(ACCOUNT, "Bravo", "bravo", agent="lucy")
        topics.link_events(ACCOUNT, "alpha", ["e1"], agent="lucy")
        topics.unlink_events(ACCOUNT, "alpha", ["e1"], agent="lucy")
        topics.rename_topic(ACCOUNT, "alpha", "Alpha v2", agent="lucy")
        topics.merge_topics(ACCOUNT, "bravo", "alpha", agent="lucy")
        topics.archive_topic(ACCOUNT, "alpha", agent="lucy")
        for stream in store.list_streams(ACCOUNT):
            for line in _raw_lines(store, stream):
                assert '"topic_id"' not in line  # decision 1
                payload = json.loads(line)["payload"]
                assert "topic_id" not in payload

    def test_no_project_context_or_external_refs(
        self, store: JsonlEventStore, topics: TopicMutations
    ) -> None:
        topics.create_topic(
            ACCOUNT,
            "Notes",
            "notes",
            agent="lucy",
            description="about things",
        )
        payload = json.loads(_raw_lines(store, "notes")[0])["payload"]
        assert set(payload) <= {"name", "slug", "description"}
        assert "project_context" not in payload
        assert "external_refs" not in payload


# ---------------------------------------------------------------------------
# Seam
# ---------------------------------------------------------------------------


class TestStoreContract:
    def test_mutations_consume_eventstore_abc(self, store: JsonlEventStore) -> None:
        assert isinstance(store, EventStore)
        m = TopicMutations(store)
        assert isinstance(m, TopicMutations)

    def test_error_hierarchy(self) -> None:
        assert issubclass(TopicNotFoundError, TopicError)
        assert issubclass(TopicArchivedError, TopicError)
