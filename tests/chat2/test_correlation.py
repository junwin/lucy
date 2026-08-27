"""Tests for the correlation to event mapping (src/chat2/correlation.py).

Covers the sidecar index functions (link_event, get_links, get_event_ids)
and the Chat2Store facade additions (link_event, get_events_by_correlation)
across the media-neutral backends: InMemoryStore and JfsChat2Primitives.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
from src.chat2.correlation import get_event_ids, get_links, link_event
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.store_primitives import Chat2Primitives, InMemoryStore, StoreKey
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_jfs(tmp_path) -> JfsChat2Primitives:
    sp = StoragePaths(str(tmp_path), "test_ns")
    return JfsChat2Primitives(JsonFileStorage(sp))


@pytest.fixture(params=["memory", "jfs"])
def store(request, tmp_path) -> Chat2Primitives:
    """Parametrized backend over InMemoryStore and JfsChat2Primitives."""
    if request.param == "memory":
        return InMemoryStore()
    return _make_jfs(tmp_path)


@pytest.fixture
def facade(store: Chat2Primitives) -> Chat2Store:
    return Chat2Store(store)


def _new_session_with_events(
    facade: Chat2Store,
    count: int,
) -> tuple[str, list[ChatEvent]]:
    meta = facade.create_session(
        user_id="user1",
        account_name="acct",
        agent_name="lucy",
    )
    events = [
        ChatEvent(
            role="user" if i % 2 == 0 else "assistant",
            actor="john" if i % 2 == 0 else "lucy",
            kind="user_message" if i % 2 == 0 else "assistant_message",
            payload=f"payload-{i}",
        )
        for i in range(count)
    ]
    facade.add_events(meta.session_id, events)
    return meta.session_id, events


# ---------------------------------------------------------------------------
# Mapping functions
# ---------------------------------------------------------------------------


class TestCorrelationMapping:
    """Tests for link_event / get_links / get_event_ids on both backends."""

    def test_link_round_trip(self, store: Chat2Primitives, facade: Chat2Store) -> None:
        """A linked event is returned by get_links and get_event_ids."""
        sid, events = _new_session_with_events(facade, 1)
        corr = str(uuid.uuid4())

        link_event(store, corr, sid, events[0].event_id)

        links = get_links(store, corr)
        assert len(links) == 1
        assert links[0].session_id == sid
        assert links[0].event_id == events[0].event_id
        assert isinstance(links[0].ts, datetime)
        assert get_event_ids(store, corr) == [events[0].event_id]

    def test_link_order_preserved(self, store: Chat2Primitives, facade: Chat2Store) -> None:
        """Links come back in write order, not event file order."""
        sid, events = _new_session_with_events(facade, 3)
        corr = str(uuid.uuid4())

        for ev in reversed(events):
            link_event(store, corr, sid, ev.event_id)

        assert get_event_ids(store, corr) == [ev.event_id for ev in reversed(events)]

    def test_n_events_per_correlation_across_sessions(
        self, store: Chat2Primitives, facade: Chat2Store
    ) -> None:
        """One correlation links N events across multiple sessions."""
        sid1, events1 = _new_session_with_events(facade, 3)
        sid2, events2 = _new_session_with_events(facade, 2)
        corr = str(uuid.uuid4())

        for ev in events1:
            link_event(store, corr, sid1, ev.event_id)
        for ev in events2:
            link_event(store, corr, sid2, ev.event_id)

        expected = [ev.event_id for ev in events1] + [ev.event_id for ev in events2]
        assert get_event_ids(store, corr) == expected
        assert len(get_links(store, corr)) == 5

    def test_link_dedupe(self, store: Chat2Primitives, facade: Chat2Store) -> None:
        """Duplicated links of the same event collapse to one (first wins)."""
        sid, events = _new_session_with_events(facade, 1)
        corr = str(uuid.uuid4())

        link_event(store, corr, sid, events[0].event_id)
        link_event(store, corr, sid, events[0].event_id)

        links = get_links(store, corr)
        assert len(links) == 1
        assert links[0].event_id == events[0].event_id

    def test_missing_correlation_empty(
        self, store: Chat2Primitives, facade: Chat2Store
    ) -> None:
        """Unknown correlation ids return [] and never raise."""
        corr = str(uuid.uuid4())
        assert get_links(store, corr) == []
        assert get_event_ids(store, corr) == []
        assert facade.get_events_by_correlation(corr) == []

    def test_falsy_correlation_noop(
        self, store: Chat2Primitives, facade: Chat2Store
    ) -> None:
        """None/'' correlation ids write nothing and never raise."""
        sid, events = _new_session_with_events(facade, 1)

        for bad in (None, ""):
            link_event(store, bad, sid, events[0].event_id)
            assert get_links(store, bad) == []
            assert get_event_ids(store, bad) == []

        assert store.list_keys(StoreKey("correlations/")) == []

    def test_invalid_correlation_id_rejected(
        self, store: Chat2Primitives, facade: Chat2Store
    ) -> None:
        """Correlation ids with '/' or '..' are rejected before key building."""
        sid, events = _new_session_with_events(facade, 1)

        for bad in ("a/b", "a..b"):
            with pytest.raises(ValueError):
                link_event(store, bad, sid, events[0].event_id)

        assert store.list_keys(StoreKey("correlations/")) == []

    def test_ts_serialized_as_iso(
        self, store: Chat2Primitives, facade: Chat2Store
    ) -> None:
        """ts is written as an ISO string and parses back to a datetime."""
        sid, events = _new_session_with_events(facade, 1)
        corr = str(uuid.uuid4())

        link_event(store, corr, sid, events[0].event_id)

        raw = store.read_text(StoreKey(f"correlations/{corr}.jsonl"))
        assert raw is not None
        assert '"ts":"' in raw
        assert "+00:00" in raw
        assert isinstance(get_links(store, corr)[0].ts, datetime)


# ---------------------------------------------------------------------------
# Facade join
# ---------------------------------------------------------------------------


class TestFacadeCorrelation:
    """Tests for Chat2Store.get_events_by_correlation."""

    def test_get_events_by_correlation_in_link_order(
        self, facade: Chat2Store
    ) -> None:
        """The facade joins linked events in link order across sessions."""
        sid1, events1 = _new_session_with_events(facade, 2)
        sid2, events2 = _new_session_with_events(facade, 1)
        corr = str(uuid.uuid4())

        facade.link_event(corr, sid1, events1[0].event_id)
        facade.link_event(corr, sid2, events2[0].event_id)
        facade.link_event(corr, sid1, events1[1].event_id)

        joined = facade.get_events_by_correlation(corr)
        assert [e.event_id for e in joined] == [
            events1[0].event_id,
            events2[0].event_id,
            events1[1].event_id,
        ]
        assert all(isinstance(e, ChatEvent) for e in joined)

    def test_facade_link_noop_falsy(self, facade: Chat2Store) -> None:
        """Facade link_event with falsy correlation is a no-op."""
        sid, events = _new_session_with_events(facade, 1)

        facade.link_event(None, sid, events[0].event_id)
        facade.link_event("", sid, events[0].event_id)

        assert facade.get_events_by_correlation(None) == []
        assert facade.get_events_by_correlation("") == []

    def test_get_events_by_correlation_skips_missing_events(
        self, store: Chat2Primitives, facade: Chat2Store
    ) -> None:
        """Linked events that no longer exist are skipped without raising."""
        sid, events = _new_session_with_events(facade, 2)
        corr = str(uuid.uuid4())

        facade.link_event(corr, sid, events[0].event_id)
        facade.link_event(corr, sid, events[1].event_id)

        store.delete(StoreKey(f"sessions/{sid}/events.jsonl"))

        joined = facade.get_events_by_correlation(corr)
        assert joined == []
