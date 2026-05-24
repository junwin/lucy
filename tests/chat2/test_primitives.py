"""
Tests for Chat v2 storage primitives (StoreKey + Chat2Primitives protocol).

Includes an in-memory fake implementation of Chat2Primitives for testing.
"""

from __future__ import annotations

from typing import Optional

import pytest

from src.chat2.store_primitives import Chat2Primitives, StoreKey


# ---------------------------------------------------------------------------
# In-memory fake implementation of Chat2Primitives
# ---------------------------------------------------------------------------

class InMemoryStore:
    """A dict-backed implementation of Chat2Primitives for testing."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def read_text(self, key: StoreKey) -> Optional[str]:
        return self._data.get(key.value)

    def write_text(self, key: StoreKey, text: str) -> None:
        self._data[key.value] = text

    def append_text(self, key: StoreKey, text: str) -> None:
        existing = self._data.get(key.value, "")
        self._data[key.value] = existing + text

    def exists(self, key: StoreKey) -> bool:
        return key.value in self._data

    def delete(self, key: StoreKey) -> None:
        self._data.pop(key.value, None)

    def list_keys(self, prefix: StoreKey) -> list[StoreKey]:
        return [StoreKey(k) for k in self._data if k.startswith(prefix.value)]


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
