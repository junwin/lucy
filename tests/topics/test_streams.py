"""
Tests for src/topics/streams.py - the EventStore seam over account-scoped
JSONL stream files (inbox + one per explicit topic).

Covers the t-streams DoD:
- inbox.jsonl created on first write; topic stream file created on
  topic_created
- writes to an archived topic's stream rejected with an explicit error
- events from two different agents append to the same topic stream (no agent
  partitioning)

Standalone (decision 4): no FCP/agent imports anywhere in this file.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.storage.interfaces import EventStore
from src.topics.schemas import (
    INBOX_STREAM,
    KIND_TOPIC_ARCHIVED,
    KIND_TOPIC_CREATED,
    KIND_TOPIC_LINK,
    TopicArchivedPayload,
    TopicCreatedPayload,
    TopicEvent,
    TopicLinkPayload,
    inbox_path,
    stream_path,
)
from src.topics.streams import (
    JsonlEventStore,
    StreamArchivedError,
    StreamError,
    StreamNotFoundError,
)

ACCOUNT = "junwin"


# ---------------------------------------------------------------------------
# Event builders (within the pinned v1 schema: topic_* kinds only)
# ---------------------------------------------------------------------------


def _created(slug: str = "my-topic", name: str = "My Topic", agent: str = "lucy") -> TopicEvent:
    return TopicEvent(
        kind=KIND_TOPIC_CREATED,
        agent=agent,
        account=ACCOUNT,
        stream=slug,
        payload=TopicCreatedPayload(name=name, slug=slug),
    )


def _link(slug: str, event_ids=None, agent: str = "lucy") -> TopicEvent:
    """A payload-bearing event appended to a topic's stream.

    Stands in for 'an event written while a topic is active': link events are
    legitimate topic-stream events in v1 (general conversation kinds arrive
    with migration/FCP integration).
    """
    return TopicEvent(
        kind=KIND_TOPIC_LINK,
        agent=agent,
        account=ACCOUNT,
        stream=slug,
        payload=TopicLinkPayload(topic=slug, event_ids=event_ids or ["e1"]),
    )


def _archived(slug: str, reason: str = "done", agent: str = "lucy") -> TopicEvent:
    return TopicEvent(
        kind=KIND_TOPIC_ARCHIVED,
        agent=agent,
        account=ACCOUNT,
        stream=slug,
        payload=TopicArchivedPayload(reason=reason),
    )


def _inbox_event(agent: str = "lucy") -> TopicEvent:
    """Stand-in for an unattributed event destined for the inbox.

    The inbox is the default destination for events not yet attributed to a
    topic. ``topic_link`` is used because the v1 schema only defines
    ``topic_*`` kinds; general conversation kinds arrive with migration/FCP
    integration.
    """
    return TopicEvent(
        kind=KIND_TOPIC_LINK,
        agent=agent,
        account=ACCOUNT,
        stream=INBOX_STREAM,
        payload=TopicLinkPayload(topic=INBOX_STREAM, event_ids=["e1"]),
    )


@pytest.fixture
def store(tmp_path: Path) -> JsonlEventStore:
    return JsonlEventStore(tmp_path)


# ---------------------------------------------------------------------------
# Inbox: default destination, created on first write
# ---------------------------------------------------------------------------


class TestInboxStream:
    def test_inbox_created_on_first_write(self, store: JsonlEventStore) -> None:
        assert not (store._data_root / inbox_path(ACCOUNT)).exists()
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event())
        assert (store._data_root / inbox_path(ACCOUNT)).exists()

    def test_inbox_is_default_destination_no_create_required(
        self, store: JsonlEventStore
    ) -> None:
        # No create_stream call needed: the inbox accepts writes immediately.
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event())
        events = store.read_events(ACCOUNT, INBOX_STREAM)
        assert len(events) == 1
        assert events[0].stream == INBOX_STREAM

    def test_inbox_preserves_append_order(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event(agent="lucy"))
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event(agent="ziggy"))
        events = store.stream_events(ACCOUNT, INBOX_STREAM)
        assert [e.agent for e in events] == ["lucy", "ziggy"]

    def test_create_stream_rejects_inbox(self, store: JsonlEventStore) -> None:
        with pytest.raises(ValueError, match="first write"):
            store.create_stream(ACCOUNT, INBOX_STREAM)


# ---------------------------------------------------------------------------
# Topic streams: created on topic_created
# ---------------------------------------------------------------------------


class TestTopicStreamCreation:
    def test_topic_stream_created_on_topic_created(self, store: JsonlEventStore) -> None:
        path = store._data_root / stream_path(ACCOUNT, "my-topic")
        assert not path.exists()
        store.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        assert path.exists()

    def test_topic_created_lands_in_its_own_stream(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        events = store.read_events(ACCOUNT, "my-topic")
        assert len(events) == 1
        assert events[0].kind == KIND_TOPIC_CREATED
        assert events[0].stream == "my-topic"

    def test_append_to_unknown_stream_rejected(self, store: JsonlEventStore) -> None:
        with pytest.raises(StreamNotFoundError):
            store.append_event(ACCOUNT, "ghost", _link("ghost"))
        # The failed append must not create the file.
        assert not (store._data_root / stream_path(ACCOUNT, "ghost")).exists()

    def test_error_is_a_stream_error(self) -> None:
        assert issubclass(StreamNotFoundError, StreamError)
        assert issubclass(StreamArchivedError, StreamError)

    def test_create_stream_explicit_and_idempotent(self, store: JsonlEventStore) -> None:
        store.create_stream(ACCOUNT, "explicit-topic")
        assert store.stream_exists(ACCOUNT, "explicit-topic")
        store.create_stream(ACCOUNT, "explicit-topic")  # no error
        # The stream accepts writes after explicit creation.
        store.append_event(ACCOUNT, "explicit-topic", _link("explicit-topic"))
        assert len(store.read_events(ACCOUNT, "explicit-topic")) == 1

    def test_stream_exists(self, store: JsonlEventStore) -> None:
        assert not store.stream_exists(ACCOUNT, "nope")
        store.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        assert store.stream_exists(ACCOUNT, "my-topic")

    def test_topic_created_slug_must_match_stream(self, store: JsonlEventStore) -> None:
        # The event is being written to stream "other-topic" (its envelope
        # stream field agrees) but its payload creates slug "my-topic".
        ev = _created("my-topic")
        ev.stream = "other-topic"
        with pytest.raises(ValueError, match="must match the stream"):
            store.append_event(ACCOUNT, "other-topic", ev)

    def test_link_target_must_match_stream(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        # Writing a link that targets "different-topic" into my-topic's stream.
        ev = _link("different-topic")
        ev.stream = "my-topic"
        with pytest.raises(ValueError, match="must match the stream"):
            store.append_event(ACCOUNT, "my-topic", ev)


# ---------------------------------------------------------------------------
# Archive freeze: event + freeze only
# ---------------------------------------------------------------------------


class TestArchiveFreeze:
    def _active_topic(self, store: JsonlEventStore, slug: str = "my-topic") -> None:
        store.append_event(ACCOUNT, slug, _created(slug))

    def test_archive_is_event_driven(self, store: JsonlEventStore) -> None:
        # Archive state is a side effect of the topic_archived event; there is
        # no separate freeze call (v1: archive = event + freeze only).
        assert not hasattr(store, "archive_stream")
        self._active_topic(store)
        assert store.is_archived(ACCOUNT, "my-topic") is False
        store.append_event(ACCOUNT, "my-topic", _archived("my-topic"))
        assert store.is_archived(ACCOUNT, "my-topic") is True

    def test_archived_stream_rejects_new_writes(self, store: JsonlEventStore) -> None:
        self._active_topic(store)
        store.append_event(ACCOUNT, "my-topic", _archived("my-topic"))
        with pytest.raises(StreamArchivedError):
            store.append_event(ACCOUNT, "my-topic", _link("my-topic"))
        # The rejected write must not have been persisted.
        events = store.read_events(ACCOUNT, "my-topic")
        assert [e.kind for e in events] == [KIND_TOPIC_CREATED, KIND_TOPIC_ARCHIVED]

    def test_archived_stream_still_queryable(self, store: JsonlEventStore) -> None:
        self._active_topic(store)
        store.append_event(ACCOUNT, "my-topic", _link("my-topic"))
        store.append_event(ACCOUNT, "my-topic", _archived("my-topic"))
        events = store.read_events(ACCOUNT, "my-topic")
        assert [e.kind for e in events] == [
            KIND_TOPIC_CREATED,
            KIND_TOPIC_LINK,
            KIND_TOPIC_ARCHIVED,
        ]

    def test_archive_state_survives_restart(self, tmp_path: Path) -> None:
        s1 = JsonlEventStore(tmp_path)
        s1.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        s1.append_event(ACCOUNT, "my-topic", _archived("my-topic"))
        s2 = JsonlEventStore(tmp_path)
        assert s2.is_archived(ACCOUNT, "my-topic") is True
        with pytest.raises(StreamArchivedError):
            s2.append_event(ACCOUNT, "my-topic", _link("my-topic"))

    def test_inbox_never_archived(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event())
        store.append_event(ACCOUNT, INBOX_STREAM, _archived(INBOX_STREAM))
        assert store.is_archived(ACCOUNT, INBOX_STREAM) is False
        # The inbox still accepts writes.
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event())
        assert len(store.read_events(ACCOUNT, INBOX_STREAM)) == 3


# ---------------------------------------------------------------------------
# No agent partitioning (decision 7)
# ---------------------------------------------------------------------------


class TestNoAgentPartitioning:
    def test_two_agents_share_one_topic_stream(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, "shared-topic", _created("shared-topic", agent="lucy"))
        store.append_event(ACCOUNT, "shared-topic", _link("shared-topic", agent="lucy"))
        store.append_event(ACCOUNT, "shared-topic", _link("shared-topic", agent="ziggy"))

        events = store.read_events(ACCOUNT, "shared-topic")
        assert [e.agent for e in events] == ["lucy", "lucy", "ziggy"]
        # One file for the topic, regardless of how many agents wrote to it.
        account_dir = store._data_root / Path(inbox_path(ACCOUNT)).parent
        files = [p.name for p in account_dir.iterdir() if p.is_file()]
        assert files == ["shared-topic.jsonl"]

    def test_agent_never_part_of_the_path(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, "shared-topic", _created("shared-topic", agent="lucy"))
        store.append_event(ACCOUNT, "shared-topic", _link("shared-topic", agent="ziggy"))
        path = store._data_root / stream_path(ACCOUNT, "shared-topic")
        assert "lucy" not in str(path)
        assert "ziggy" not in str(path)
        raw = path.read_text(encoding="utf-8")
        assert "lucy" in raw and "ziggy" in raw  # both present as metadata


# ---------------------------------------------------------------------------
# Reading events
# ---------------------------------------------------------------------------


class TestReadEvents:
    def test_order_and_limit(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        store.append_event(ACCOUNT, "my-topic", _link("my-topic", event_ids=["e1"]))
        store.append_event(ACCOUNT, "my-topic", _link("my-topic", event_ids=["e2"]))
        assert len(store.read_events(ACCOUNT, "my-topic")) == 3
        assert len(store.read_events(ACCOUNT, "my-topic", limit=2)) == 2
        assert [e.kind for e in store.read_events(ACCOUNT, "my-topic", limit=1)] == [
            KIND_TOPIC_CREATED
        ]

    def test_time_bounds_inclusive(self, store: JsonlEventStore) -> None:
        t0 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
        t1 = t0 + timedelta(minutes=1)
        t2 = t0 + timedelta(minutes=2)
        created = _created("my-topic", agent="a")
        created.ts = t0
        store.append_event(ACCOUNT, "my-topic", created)
        ev1 = _link("my-topic", event_ids=["e1"], agent="a")
        ev1.ts = t1
        ev2 = _link("my-topic", event_ids=["e2"], agent="a")
        ev2.ts = t2
        store.append_event(ACCOUNT, "my-topic", ev1)
        store.append_event(ACCOUNT, "my-topic", ev2)

        got = store.read_events(ACCOUNT, "my-topic", start_ts=t1, end_ts=t2)
        assert [e.ts for e in got] == [t1, t2]

        # Naive bounds are assumed UTC, like the schema's ts normalization.
        got = store.read_events(ACCOUNT, "my-topic", start_ts=t1.replace(tzinfo=None))
        assert len(got) == 2

    def test_missing_stream_yields_nothing(self, store: JsonlEventStore) -> None:
        assert list(store.stream_events(ACCOUNT, "ghost")) == []
        assert store.read_events(ACCOUNT, "ghost") == []

    def test_roundtrip_across_instances(self, tmp_path: Path) -> None:
        s1 = JsonlEventStore(tmp_path)
        s1.append_event(ACCOUNT, "my-topic", _created("my-topic"))
        s1.append_event(ACCOUNT, "my-topic", _link("my-topic", event_ids=["e1"]))
        s2 = JsonlEventStore(tmp_path)
        events = s2.read_events(ACCOUNT, "my-topic")
        assert len(events) == 2
        assert events[0].kind == KIND_TOPIC_CREATED

    def test_persisted_line_is_json_and_append_only(self, store: JsonlEventStore) -> None:
        ev = _created("my-topic")
        store.append_event(ACCOUNT, "my-topic", ev)
        path = store._data_root / stream_path(ACCOUNT, "my-topic")
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        assert lines[0] == ev.model_dump_json()
        # Appending never rewrites earlier lines.
        store.append_event(ACCOUNT, "my-topic", _link("my-topic"))
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert lines[0] == ev.model_dump_json()


# ---------------------------------------------------------------------------
# Listing streams
# ---------------------------------------------------------------------------


class TestListStreams:
    def test_empty_account(self, store: JsonlEventStore) -> None:
        assert store.list_streams(ACCOUNT) == []

    def test_returns_inbox_and_topic_streams_sorted(self, store: JsonlEventStore) -> None:
        store.append_event(ACCOUNT, INBOX_STREAM, _inbox_event())
        store.append_event(ACCOUNT, "zebra", _created("zebra"))
        store.append_event(ACCOUNT, "alpha", _created("alpha"))
        assert store.list_streams(ACCOUNT) == ["alpha", "inbox", "zebra"]


# ---------------------------------------------------------------------------
# Seam + envelope integrity
# ---------------------------------------------------------------------------


class TestStoreContract:
    def test_implements_eventstore_abc(self, store: JsonlEventStore) -> None:
        assert isinstance(store, EventStore)

    def test_account_mismatch_rejected(self, store: JsonlEventStore) -> None:
        ev = _created("my-topic")
        ev.account = "someone-else"
        with pytest.raises(ValueError, match="does not match account"):
            store.append_event(ACCOUNT, "my-topic", ev)

    def test_stream_field_mismatch_rejected(self, store: JsonlEventStore) -> None:
        ev = _created("my-topic")
        ev.stream = "inbox"
        with pytest.raises(ValueError, match="does not match stream"):
            store.append_event(ACCOUNT, "my-topic", ev)

    def test_non_topic_event_rejected(self, store: JsonlEventStore) -> None:
        with pytest.raises(TypeError, match="TopicEvent"):
            store.append_event(ACCOUNT, "my-topic", {"kind": "topic_created"})  # type: ignore[arg-type]
