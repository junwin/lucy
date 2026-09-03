"""
Tests for Chat v2 storage primitives (StoreKey + Chat2Primitives protocol).

Uses the InMemoryStore fake from src.chat2.store_primitives as the
reference implementation for protocol conformance tests.
"""

from __future__ import annotations

import pytest

from src.chat2.store_primitives import Chat2Primitives, InMemoryStore, StoreKey


# Verify InMemoryStore satisfies the Chat2Primitives protocol at runtime
@pytest.fixture
def store() -> Chat2Primitives:
    return InMemoryStore()


# ---------------------------------------------------------------------------
# StoreKey tests
# ---------------------------------------------------------------------------

class TestStoreKey:
    def test_valid_key(self) -> None:
        key = StoreKey("sessions/abc-123/meta.json")
        assert key.value == "sessions/abc-123/meta.json"
        assert str(key) == "sessions/abc-123/meta.json"

    def test_rejects_leading_slash(self) -> None:
        with pytest.raises(ValueError, match="no leading '/'"):
            StoreKey("/sessions/abc/meta.json")

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(ValueError, match="must not contain '..'"):
            StoreKey("sessions/../meta.json")

    def test_rejects_non_string(self) -> None:
        with pytest.raises(TypeError):
            StoreKey(123)  # type: ignore[arg-type]

    def test_equality(self) -> None:
        a = StoreKey("sessions/x/events.jsonl")
        b = StoreKey("sessions/x/events.jsonl")
        c = StoreKey("sessions/y/events.jsonl")
        assert a == b
        assert a != c

    def test_hashable(self) -> None:
        d = {StoreKey("a"): 1, StoreKey("b"): 2}
        assert d[StoreKey("a")] == 1


# ---------------------------------------------------------------------------
# Chat2Primitives protocol tests (using InMemoryStore)
# ---------------------------------------------------------------------------

class TestChat2Primitives:
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

    def test_exists(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/exists.txt")
        assert not store.exists(key)
        store.write_text(key, "now it exists")
        assert store.exists(key)

    def test_delete(self, store: Chat2Primitives) -> None:
        key = StoreKey("test/delete_me.txt")
        store.write_text(key, "bye")
        assert store.exists(key)
        store.delete(key)
        assert not store.exists(key)

    def test_delete_nonexistent_is_noop(self, store: Chat2Primitives) -> None:
        """Deleting a key that doesn't exist should not raise."""
        store.delete(StoreKey("ghost"))  # should not raise

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

    def test_protocol_runtime_checkable(self) -> None:
        """InMemoryStore should satisfy the Chat2Primitives protocol."""
        assert isinstance(InMemoryStore(), Chat2Primitives)


# ---------------------------------------------------------------------------
# Log ops (read_lines / append_lines / truncate)
# ---------------------------------------------------------------------------

class TestLogOps:
    def test_append_and_read_lines_roundtrip(self, store: Chat2Primitives) -> None:
        key = StoreKey("logs/events.jsonl")
        store.append_lines(key, ["a", "b", "c"])
        assert store.read_lines(key) == ["a", "b", "c"]

    def test_append_lines_preserves_batch_order(self, store: Chat2Primitives) -> None:
        key = StoreKey("logs/events.jsonl")
        store.append_lines(key, ["a", "b"])
        store.append_lines(key, ["c", "d"])
        assert store.read_lines(key) == ["a", "b", "c", "d"]

    def test_append_lines_empty_batch_is_noop(self, store: Chat2Primitives) -> None:
        key = StoreKey("logs/events.jsonl")
        store.append_lines(key, ["a"])
        store.append_lines(key, [])
        assert store.read_lines(key) == ["a"]

    def test_read_lines_missing_key(self, store: Chat2Primitives) -> None:
        assert store.read_lines(StoreKey("logs/missing.jsonl")) is None

    def test_truncate_clears_log_keeps_doc(self, store: Chat2Primitives) -> None:
        key = StoreKey("sessions/s1/events.jsonl")
        store.write_text(key, "")
        store.append_lines(key, ["e1", "e2"])
        store.truncate(key)
        assert store.read_lines(key) is None
        assert store.exists(key)
        assert store.read_text(key) == ""

    def test_delete_removes_doc_and_log(self, store: Chat2Primitives) -> None:
        key = StoreKey("sessions/s1/events.jsonl")
        store.write_text(key, "")
        store.append_lines(key, ["e1"])
        store.delete(key)
        assert not store.exists(key)
        assert store.read_text(key) is None
        assert store.read_lines(key) is None

    def test_list_keys_includes_log_keys(self, store: Chat2Primitives) -> None:
        store.append_lines(StoreKey("sessions/a/events.jsonl"), ["e1"])
        store.write_text(StoreKey("sessions/a/meta.json"), "{}")
        keys = store.list_keys(StoreKey("sessions/"))
        assert keys == [
            StoreKey("sessions/a/events.jsonl"),
            StoreKey("sessions/a/meta.json"),
        ]
