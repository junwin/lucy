"""
Tests for FileChat2Primitives (src/chat2/fs_primitives.py).

Uses tmp_path to create an isolated filesystem for each test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.store_primitives import Chat2Primitives, StoreKey


@pytest.fixture
def store(tmp_path: Path) -> Chat2Primitives:
    return FileChat2Primitives(tmp_path)


# ---------------------------------------------------------------------------
# Basic read/write/exists/delete
# ---------------------------------------------------------------------------

class TestReadWrite:
    def test_write_and_read_text(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/hello.txt")
        store.write_text(key, "Hello, world!")
        assert store.read_text(key) == "Hello, world!"

    def test_read_text_missing_key(self, store: Chat2Primitives) -> None:
        key = StoreKey("nonexistent")
        assert store.read_text(key) is None

    def test_write_overwrites(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/overwrite.txt")
        store.write_text(key, "first")
        store.write_text(key, "second")
        assert store.read_text(key) == "second"

    def test_write_creates_parent_dirs(self, store: Chat2Primitives) -> None:
        key = StoreKey("a/b/c/d/file.txt")
        store.write_text(key, "deep")
        assert store.read_text(key) == "deep"


class TestAppend:
    def test_append_text(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/log.txt")
        store.append_text(key, "line1\n")
        store.append_text(key, "line2\n")
        assert store.read_text(key) == "line1\nline2\n"

    def test_append_to_nonexistent_key(self, store: Chat2Primitives) -> None:
        """Appending to a key that doesn't exist yet should create it."""
        key = StoreKey("test/new.txt")
        store.append_text(key, "fresh")
        assert store.read_text(key) == "fresh"

    def test_append_creates_parent_dirs(self, store: Chat2Primitives) -> None:
        key = StoreKey("a/b/c/log.txt")
        store.append_text(key, "data\n")
        assert store.read_text(key) == "data\n"


class TestExists:
    def test_exists_after_write(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/exists.txt")
        assert not store.exists(key)
        store.write_text(key, "now it exists")
        assert store.exists(key)

    def test_exists_after_append(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/appended.txt")
        store.append_text(key, "data")
        assert store.exists(key)


class TestDelete:
    def test_delete(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/delete_me.txt")
        store.write_text(key, "bye")
        assert store.exists(key)
        store.delete(key)
        assert not store.exists(key)

    def test_delete_nonexistent_is_noop(self, store: Chat2Primitives) -> None:
        """Deleting a key that doesn't exist should not raise."""
        store.delete(StoreKey("ghost"))  # should not raise


# ---------------------------------------------------------------------------
# list_keys
# ---------------------------------------------------------------------------

class TestListKeys:
    def test_list_keys(self, store: Chat2Primitives) -> None:
        store.write_text(StoreKey("sessions/a/meta.json"), "{}")
        store.write_text(StoreKey("sessions/a/events.jsonl"), "")
        store.write_text(StoreKey("sessions/b/meta.json"), "{}")
        store.write_text(StoreKey("other/x.txt"), "data")

        prefix = StoreKey("sessions/")
        keys = store.list_keys(prefix)
        assert len(keys) == 3
        assert all(k.value.startswith("sessions/") for k in keys)

    def test_list_keys_no_match(self, store: Chat2Primitives) -> None:
        keys = store.list_keys(StoreKey("nothing/"))
        assert keys == []

    def test_list_keys_empty_prefix(self, store: Chat2Primitives) -> None:
        """Listing with an empty prefix should return all keys."""
        store.write_text(StoreKey("a.txt"), "1")
        store.write_text(StoreKey("b.txt"), "2")
        keys = store.list_keys(StoreKey(""))
        assert len(keys) == 2


# ---------------------------------------------------------------------------
# Security: path traversal protection
# ---------------------------------------------------------------------------

class TestPathTraversal:
    def test_rejects_dotdot_in_key(self, store: Chat2Primitives) -> None:
        """StoreKey validation should catch '..' before it reaches the adapter."""
        with pytest.raises(ValueError, match="must not contain '..'"):
            StoreKey("sessions/../etc/passwd")

    def test_rejects_absolute_key(self, store: Chat2Primitives) -> None:
        """StoreKey validation should catch leading '/'."""
        with pytest.raises(ValueError, match="no leading '/'"):
            StoreKey("/etc/passwd")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

class TestProtocol:
    def test_is_chat2_primitives(self, tmp_path: Path) -> None:
        """FileChat2Primitives should satisfy the Chat2Primitives protocol."""
        assert isinstance(FileChat2Primitives(tmp_path), Chat2Primitives)


# ---------------------------------------------------------------------------
# Integration: JSONL store functions with FileChat2Primitives
# ---------------------------------------------------------------------------

class TestJsonlStoreIntegration:
    """Re-run key JSONL store scenarios using FileChat2Primitives."""

    def test_create_session_and_append(self, store: Chat2Primitives) -> None:
        from src.chat2.jsonl_store import (
            append_event,
            create_session,
            get_session_meta,
            stream_events,
        )
        from src.chat2.models import ChatEvent

        meta = create_session(
            store,
            user_id="user-1",
            account_name="acme",
            agent_name="lucy",
            friendly_name="fs-test",
        )
        sid = meta.session_id

        # Verify files exist on disk
        meta_key = StoreKey(f"sessions/{sid}/meta.json")
        events_key = StoreKey(f"sessions/{sid}/events.jsonl")
        assert store.exists(meta_key)
        assert store.exists(events_key)

        # Append events
        ev1 = ChatEvent(role="user", actor="john", kind="user_message", payload="Hello from fs")
        ev2 = ChatEvent(role="assistant", actor="lucy", kind="assistant_message", payload="Hi back")
        append_event(store, sid, ev1)
        append_event(store, sid, ev2)

        # Stream back
        events = list(stream_events(store, sid))
        assert len(events) == 2
        assert events[0].payload == "Hello from fs"
        assert events[1].payload == "Hi back"

        # Meta updated
        fetched = get_session_meta(store, sid)
        assert fetched is not None
        assert fetched.friendly_name == "fs-test"
        assert fetched.updated_at > meta.updated_at

    def test_reset_session(self, store: Chat2Primitives) -> None:
        from src.chat2.jsonl_store import (
            append_event,
            create_session,
            reset_session_events,
            stream_events,
        )
        from src.chat2.models import ChatEvent

        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id

        append_event(store, sid, ChatEvent(role="user", actor="john", kind="user_message", payload="Hi"))
        assert len(list(stream_events(store, sid))) == 1

        reset_session_events(store, sid)
        assert len(list(stream_events(store, sid))) == 0

    def test_delete_session(self, store: Chat2Primitives) -> None:
        from src.chat2.jsonl_store import create_session, delete_session, get_session_meta

        meta = create_session(store, user_id="u1", account_name="a", agent_name="b")
        sid = meta.session_id
        assert get_session_meta(store, sid) is not None

        delete_session(store, sid)
        assert get_session_meta(store, sid) is None
