"""Tests for JfsChat2Primitives adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
from src.chat2.jsonl_store import (
    append_event,
    create_session,
    get_session_meta,
    read_events,
    reset_session_events,
    stream_events,
)
from src.chat2.models import ChatEvent, SessionLinks
from src.chat2.store_primitives import StoreKey
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storage(tmp_path: Path) -> JsonFileStorage:
    """Create a JsonFileStorage backed by a temp directory."""
    sp = StoragePaths(str(tmp_path), "test_ns")
    return JsonFileStorage(sp)


def _make_adapter(tmp_path: Path) -> JfsChat2Primitives:
    """Create a JfsChat2Primitives backed by a temp directory."""
    storage = _make_storage(tmp_path)
    return JfsChat2Primitives(storage)


# ---------------------------------------------------------------------------
# Primitive-level tests
# ---------------------------------------------------------------------------


class TestJfsPrimitives:
    """Test that JfsChat2Primitives correctly implements Chat2Primitives."""

    def test_read_write_roundtrip(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("test/hello.txt")

        adapter.write_text(key, "world")
        assert adapter.read_text(key) == "world"

    def test_read_missing_key(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("test/missing.txt")

        assert adapter.read_text(key) is None

    def test_append_text(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("test/log.txt")

        adapter.append_text(key, "line1\n")
        adapter.append_text(key, "line2\n")

        content = adapter.read_text(key)
        assert content == "line1\nline2\n"

    def test_exists(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("test/exists.txt")

        assert not adapter.exists(key)
        adapter.write_text(key, "hello")
        assert adapter.exists(key)

    def test_delete(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("test/delete_me.txt")

        adapter.write_text(key, "bye")
        assert adapter.exists(key)

        adapter.delete(key)
        assert not adapter.exists(key)

    def test_delete_missing_is_noop(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("test/never_existed.txt")

        # Should not raise
        adapter.delete(key)

    def test_list_keys(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        adapter.write_text(StoreKey("sessions/a/meta.json"), "{}")
        adapter.write_text(StoreKey("sessions/a/events.jsonl"), "")
        adapter.write_text(StoreKey("sessions/b/meta.json"), "{}")

        keys = adapter.list_keys(StoreKey("sessions"))
        assert len(keys) == 3
        assert StoreKey("sessions/a/meta.json") in keys
        assert StoreKey("sessions/a/events.jsonl") in keys
        assert StoreKey("sessions/b/meta.json") in keys

    def test_list_keys_empty_prefix(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        keys = adapter.list_keys(StoreKey("nonexistent"))
        assert keys == []

    def test_write_creates_parent_dirs(self, tmp_path):
        adapter = _make_adapter(tmp_path)
        key = StoreKey("deeply/nested/path/file.txt")

        adapter.write_text(key, "content")
        assert adapter.exists(key)

    def test_path_traversal_blocked_by_storekey(self, tmp_path):
        """StoreKey validation catches '..' before it reaches the adapter."""
        adapter = _make_adapter(tmp_path)

        with pytest.raises(ValueError, match="must not contain"):
            adapter.read_text(StoreKey("../../etc/passwd"))

    def test_storage_root_is_under_chat2(self, tmp_path):
        """Verify data is stored under <base>/chat2/, not at the base level."""
        storage = _make_storage(tmp_path)
        adapter = JfsChat2Primitives(storage)

        key = StoreKey("test/file.txt")
        adapter.write_text(key, "data")

        # Should be under chat2 subdirectory
        expected = storage.storage_paths.base / "chat2" / "test" / "file.txt"
        assert expected.exists()


# ---------------------------------------------------------------------------
# Integration tests: JFS adapter + jsonl_store functions
# ---------------------------------------------------------------------------


class TestJfsIntegration:
    """Test that jsonl_store functions work correctly with JfsChat2Primitives."""

    def test_create_session_and_get_meta(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        meta = create_session(
            adapter,
            user_id="user1",
            account_name="acct1",
            agent_name="lucy",
            friendly_name="test-session",
        )

        assert meta.session_id is not None
        assert meta.user_id == "user1"
        assert meta.account_name == "acct1"
        assert meta.agent_name == "lucy"
        assert meta.friendly_name == "test-session"

        # Read back
        loaded = get_session_meta(adapter, meta.session_id)
        assert loaded is not None
        assert loaded.session_id == meta.session_id
        assert loaded.friendly_name == "test-session"

    def test_append_and_stream_events(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        meta = create_session(adapter, user_id="u1", account_name="a1", agent_name="lucy")

        event1 = ChatEvent(role="user", actor="john", kind="user_message", payload="hello")
        event2 = ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="hi there")

        append_event(adapter, meta.session_id, event1)
        append_event(adapter, meta.session_id, event2)

        events = list(stream_events(adapter, meta.session_id))
        assert len(events) == 2
        assert events[0].payload == "hello"
        assert events[1].payload == "hi there"

    def test_read_events_with_filters(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        meta = create_session(adapter, user_id="u1", account_name="a1", agent_name="lucy")

        append_event(adapter, meta.session_id, ChatEvent(role="user", actor="john", kind="user_message", payload="q1"))
        append_event(adapter, meta.session_id, ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="a1"))
        append_event(adapter, meta.session_id, ChatEvent(role="user", actor="john", kind="user_message", payload="q2"))

        # Filter by role
        user_events = read_events(adapter, meta.session_id, role_filter="user")
        assert len(user_events) == 2
        assert all(e.role == "user" for e in user_events)

        # Filter by actor
        lucy_events = read_events(adapter, meta.session_id, actor_filter="lucy")
        assert len(lucy_events) == 1
        assert lucy_events[0].actor == "lucy"

    def test_reset_session_events(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        meta = create_session(adapter, user_id="u1", account_name="a1", agent_name="lucy")
        append_event(adapter, meta.session_id, ChatEvent(role="user", actor="john", kind="user_message", payload="hello"))

        assert len(list(stream_events(adapter, meta.session_id))) == 1

        reset_session_events(adapter, meta.session_id)

        # Events should be cleared
        assert len(list(stream_events(adapter, meta.session_id))) == 0

        # Meta should still exist
        loaded = get_session_meta(adapter, meta.session_id)
        assert loaded is not None

    def test_session_with_links(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        links = SessionLinks(internal_session_id="00000000-0000-0000-0000-000000000001")
        meta = create_session(
            adapter,
            user_id="u1",
            account_name="a1",
            agent_name="lucy",
            links=links,
            participants=["john", "lucy"],
        )

        loaded = get_session_meta(adapter, meta.session_id)
        assert loaded is not None
        assert loaded.links is not None
        assert loaded.links.internal_session_id == "00000000-0000-0000-0000-000000000001"
        assert loaded.participants == ["john", "lucy"]

    def test_missing_session_returns_none(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        meta = get_session_meta(adapter, "00000000-0000-0000-0000-000000000000")
        assert meta is None

    def test_reset_nonexistent_session_raises(self, tmp_path):
        adapter = _make_adapter(tmp_path)

        with pytest.raises(ValueError, match="not found"):
            reset_session_events(adapter, "00000000-0000-0000-0000-000000000000")
