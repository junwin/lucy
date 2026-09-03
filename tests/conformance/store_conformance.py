"""
Conformance suite for the generic-store doc/log protocol (chat2 primitives).

Every test in this file is parameterized over three backend factories —
memory, file, sqlite — and must pass identically on all of them. That is
what makes the backends interchangeable: a consumer (Chat2Store facade,
jsonl_store, correlation) must not be able to tell which backend it is
talking to.

Protocol under test (the "generic store"):

  Document ops   read_text / write_text / exists / delete
  Log ops        read_lines / append_lines / truncate   (append-only JSONL)
  Namespace      list_keys(prefix)

The SQLite backend (SqliteChat2Primitives) is the reference implementation:
documents live in a ``kv`` table and log lines in a ``logs`` table, so a
document and a log can share one StoreKey (e.g. the empty ``events.jsonl``
placeholder written by ``create_session`` plus the appended event lines).
The memory and file factories use the production InMemoryStore and
FileChat2Primitives directly, since they now implement the log ops
natively: documents and logs share one store (a dict sidecar in memory,
a single file per key on disk), mirroring the kv/logs split.

Run:  pytest tests/conformance/store_conformance.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Protocol, Union, runtime_checkable

import pytest

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import InMemoryStore, StoreKey


# ---------------------------------------------------------------------------
# The doc/log protocol every interchangeable backend implements
# ---------------------------------------------------------------------------

@runtime_checkable
class GenericStore(Protocol):
    """Minimal doc/log storage protocol shared by all backends.

    Doc ops match Chat2Primitives (read_text / write_text / exists /
    delete); log ops are the append-only line stream used for JSONL event
    logs (read_lines / append_lines / truncate).
    """

    def read_text(self, key: Union[StoreKey, str]) -> Optional[str]:
        """Return the document at *key*, or None if it does not exist."""
        ...

    def write_text(self, key: Union[StoreKey, str], text: str) -> None:
        """Atomically replace the document at *key*."""
        ...

    def exists(self, key: Union[StoreKey, str]) -> bool:
        """Return True if *key* has a document or log rows."""
        ...

    def delete(self, key: Union[StoreKey, str]) -> None:
        """Remove *key* entirely. No-op if it does not exist."""
        ...

    def read_lines(self, key: Union[StoreKey, str]) -> Optional[List[str]]:
        """Return log lines at *key* in append order, or None if missing."""
        ...

    def append_lines(self, key: Union[StoreKey, str], lines: Iterable[str]) -> None:
        """Append *lines* to the log at *key*, preserving order."""
        ...

    def truncate(self, key: Union[StoreKey, str]) -> None:
        """Clear the log at *key*, keeping any document at the same key."""
        ...

    def list_keys(self, prefix: Union[StoreKey, str]) -> List[StoreKey]:
        """Return all keys starting with *prefix* ('%' and '_' literal)."""
        ...


# ---------------------------------------------------------------------------
# Factories + parameterized fixture
# ---------------------------------------------------------------------------

def _memory_factory(tmp_path: Path) -> GenericStore:
    return InMemoryStore()


def _file_factory(tmp_path: Path) -> GenericStore:
    return FileChat2Primitives(tmp_path / "fs")


def _sqlite_factory(tmp_path: Path) -> GenericStore:
    return SqliteChat2Primitives(tmp_path / "store.db")


STORE_FACTORIES = [
    pytest.param(_memory_factory, id="memory"),
    pytest.param(_file_factory, id="file"),
    pytest.param(_sqlite_factory, id="sqlite"),
]


@pytest.fixture(params=STORE_FACTORIES)
def store(request: pytest.FixtureRequest, tmp_path: Path) -> GenericStore:
    """A fresh backend instance for one test, per factory."""
    instance = request.param(tmp_path)
    yield instance
    close = getattr(instance, "close", None)
    if callable(close):
        close()


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_backends_implement_generic_store_protocol(store: GenericStore) -> None:
    """All three factories must satisfy the doc/log protocol."""
    assert isinstance(store, GenericStore)


# ---------------------------------------------------------------------------
# Document ops
# ---------------------------------------------------------------------------

class TestDocProtocol:
    def test_doc_roundtrip(self, store: GenericStore) -> None:
        key = StoreKey("docs/hello.txt")
        store.write_text(key, "Hello, world!")
        assert store.read_text(key) == "Hello, world!"

    def test_atomic_replace(self, store: GenericStore) -> None:
        key = StoreKey("docs/replace.txt")
        store.write_text(key, "first")
        store.write_text(key, "second")
        assert store.read_text(key) == "second"
        # A replace must never leave partial or concatenated content.
        big = "x" * 4096
        store.write_text(key, big)
        assert store.read_text(key) == big

    def test_missing_key_returns_none(self, store: GenericStore) -> None:
        assert store.read_text(StoreKey("missing/doc.txt")) is None
        assert store.read_lines(StoreKey("missing/events.jsonl")) is None
        assert not store.exists(StoreKey("missing/any"))
        assert store.list_keys(StoreKey("missing/")) == []


# ---------------------------------------------------------------------------
# Log ops
# ---------------------------------------------------------------------------

class TestLogProtocol:
    def test_append_order_1000_lines(self, store: GenericStore) -> None:
        key = StoreKey("sessions/s1/events.jsonl")
        lines = [f"line-{i:04d}" for i in range(1000)]
        store.append_lines(key, lines)
        assert store.read_lines(key) == lines
        # An empty batch is a no-op and must not disturb the sequence.
        store.append_lines(key, [])
        assert store.read_lines(key) == lines
        # Later batches must continue the sequence in append order.
        more = [f"more-{i:04d}" for i in range(500)]
        store.append_lines(key, more)
        assert store.read_lines(key) == lines + more

    def test_truncate_keeps_key(self, store: GenericStore) -> None:
        key = StoreKey("sessions/s1/events.jsonl")
        store.write_text(key, "")  # placeholder doc, like create_session
        store.append_lines(key, ["e1", "e2"])
        assert store.read_lines(key) == ["e1", "e2"]
        store.truncate(key)
        assert store.read_lines(key) is None
        assert store.exists(key)  # key kept
        assert store.read_text(key) == ""  # placeholder doc preserved
        assert store.list_keys(StoreKey("sessions/")) == [key]

    def test_delete_idempotent(self, store: GenericStore) -> None:
        key = StoreKey("sessions/s2/events.jsonl")
        store.write_text(key, "doc")
        store.append_lines(key, ["a", "b"])
        store.delete(key)
        assert not store.exists(key)
        assert store.read_text(key) is None
        assert store.read_lines(key) is None
        assert store.list_keys(StoreKey("sessions/")) == []
        store.delete(key)  # deleting a missing key must not raise
        assert not store.exists(key)


# ---------------------------------------------------------------------------
# Namespace (list_keys)
# ---------------------------------------------------------------------------

class TestNamespace:
    def test_list_keys_prefix_escaping(self, store: GenericStore) -> None:
        store.write_text(StoreKey("sessions/a%b/meta.json"), "{}")
        store.write_text(StoreKey("sessions/a_b/meta.json"), "{}")
        store.write_text(StoreKey("sessions/ab/meta.json"), "{}")
        store.write_text(StoreKey("sessions/axb/meta.json"), "{}")

        # '%' and '_' inside the prefix are literal, not SQL wildcards.
        assert store.list_keys(StoreKey("sessions/a%b/")) == [
            StoreKey("sessions/a%b/meta.json")
        ]
        assert store.list_keys(StoreKey("sessions/a_b/")) == [
            StoreKey("sessions/a_b/meta.json")
        ]
        assert store.list_keys(StoreKey("sessions/ab/")) == [
            StoreKey("sessions/ab/meta.json")
        ]
        assert store.list_keys(StoreKey("sessions/axb/")) == [
            StoreKey("sessions/axb/meta.json")
        ]

        # The parent prefix still sees all four keys.
        assert store.list_keys(StoreKey("sessions/")) == [
            StoreKey("sessions/a%b/meta.json"),
            StoreKey("sessions/a_b/meta.json"),
            StoreKey("sessions/ab/meta.json"),
            StoreKey("sessions/axb/meta.json"),
        ]

    def test_list_keys_no_match(self, store: GenericStore) -> None:
        assert store.list_keys(StoreKey("nothing/")) == []


# ---------------------------------------------------------------------------
# Key validation
# ---------------------------------------------------------------------------

class TestKeyValidation:
    def test_rejects_leading_slash(self, store: GenericStore) -> None:
        with pytest.raises(ValueError):
            store.read_text(StoreKey("/abs"))
        with pytest.raises(ValueError):
            store.write_text(StoreKey("/abs"), "x")
        with pytest.raises(ValueError):
            store.exists(StoreKey("/abs"))
        with pytest.raises(ValueError):
            store.delete(StoreKey("/abs"))
        with pytest.raises(ValueError):
            store.list_keys(StoreKey("/abs/"))
        # Raw strings go through the same StoreKey validation.
        with pytest.raises(ValueError):
            store.read_text("/abs")
        with pytest.raises(ValueError):
            store.write_text("/abs", "x")

    def test_rejects_dotdot(self, store: GenericStore) -> None:
        with pytest.raises(ValueError):
            store.read_text(StoreKey("sessions/../meta.json"))
        with pytest.raises(ValueError):
            store.write_text(StoreKey("a/../b"), "x")
        with pytest.raises(ValueError):
            store.exists(StoreKey("sessions/../x"))
        with pytest.raises(ValueError):
            store.delete(StoreKey("sessions/../x"))
        with pytest.raises(ValueError):
            store.read_text("sessions/../meta.json")
