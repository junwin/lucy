"""Tests for PrimitivesEmbeddingStore — the embedding store as a second
consumer of the generic-store doc/log protocol.

The suite is parameterized over the three production backends (memory,
file, sqlite) exactly like ``tests/conformance/store_conformance.py``:
if a backend passes conformance, PrimitivesEmbeddingStore must behave
identically on it. That is what makes the backends interchangeable.

Also includes a parity test against the existing JsonFileStorage
embedding store (same on-disk files) and a reopen-persistence test for
the persistent backends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List

import pytest

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import InMemoryStore
from src.storage.interfaces import EmbeddingStore
from src.storage.json_file_storage import JsonFileStorage
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import (
    PrimitivesEmbeddingStore,
    build_primitives_embedding_store,
)
from src.storage_paths.storage_paths import StoragePaths


# ---------------------------------------------------------------------------
# Backend factories (mirror conformance/store_conformance.py)
# ---------------------------------------------------------------------------

def _memory_factory(tmp_path: Path) -> Any:
    return InMemoryStore()


def _file_factory(tmp_path: Path) -> Any:
    return FileChat2Primitives(tmp_path / "fs")


def _sqlite_factory(tmp_path: Path) -> Any:
    return SqliteChat2Primitives(tmp_path / "store.db")


BACKEND_FACTORIES = [
    pytest.param(_memory_factory, id="memory"),
    pytest.param(_file_factory, id="file"),
    pytest.param(_sqlite_factory, id="sqlite"),
]


@pytest.fixture(params=BACKEND_FACTORIES)
def store(request: pytest.FixtureRequest, tmp_path: Path) -> PrimitivesEmbeddingStore:
    """A PrimitivesEmbeddingStore over a fresh backend, per factory."""
    backend = request.param(tmp_path)
    yield PrimitivesEmbeddingStore(backend)
    close = getattr(backend, "close", None)
    if callable(close):
        close()


def _record(
    record_id: str = "rec1",
    namespace: str = "documents",
    account: str = "junwin",
    vector: List[float] | None = None,
    source_type: str = "document",
    source_id: str = "src-1",
    metadata: dict | None = None,
) -> EmbeddingRecord:
    return EmbeddingRecord(
        id=record_id,
        namespace=namespace,
        account_name=account,
        vector=vector if vector is not None else [1.0, 0.0, 0.0],
        source_type=source_type,
        source_id=source_id,
        source_metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Interface conformance
# ---------------------------------------------------------------------------

def test_implements_embedding_store_interface(store: PrimitivesEmbeddingStore) -> None:
    assert isinstance(store, EmbeddingStore)


# ---------------------------------------------------------------------------
# Upsert / query
# ---------------------------------------------------------------------------

class TestUpsertQuery:
    def test_upsert_query_roundtrip(self, store: PrimitivesEmbeddingStore) -> None:
        rec = _record(
            record_id="rec-1",
            namespace="documents",
            account="junwin",
            vector=[1.0, 0.0, 0.0],
            source_type="document",
            source_id="src-1",
            metadata={"path": "/tmp/note.md"},
        )
        store.upsert_embedding(rec)

        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
            top_k=10,
        )
        assert len(results) == 1
        got, score = results[0]
        assert score == pytest.approx(1.0)
        assert got.id == "rec-1"
        assert got.namespace == "documents"
        assert got.account_name == "junwin"
        assert got.source_type == "document"
        assert got.source_id == "src-1"
        assert got.source_metadata == {"path": "/tmp/note.md"}
        assert got.vector == [1.0, 0.0, 0.0]

    def test_upsert_overwrites_same_id(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(_record(record_id="rec", vector=[1.0, 0.0, 0.0]))
        store.upsert_embedding(_record(record_id="rec", vector=[0.0, 1.0, 0.0]))

        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[0.0, 1.0, 0.0],
        )
        assert len(results) == 1  # latest wins, no duplicates
        assert results[0][1] == pytest.approx(1.0)

    def test_query_top_k_sorted(self, store: PrimitivesEmbeddingStore) -> None:
        # q = [1,0,0]; nearest is rec-a, then rec-c, then rec-b
        store.upsert_embedding(_record(record_id="rec-a", vector=[1.0, 0.0, 0.0]))
        store.upsert_embedding(_record(record_id="rec-b", vector=[0.0, 1.0, 0.0]))
        store.upsert_embedding(_record(record_id="rec-c", vector=[0.9, 0.1, 0.0]))

        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
            top_k=2,
        )
        assert [r.id for r, _ in results] == ["rec-a", "rec-c"]
        assert results[0][1] > results[1][1]

    def test_query_missing_namespace_returns_empty(
        self, store: PrimitivesEmbeddingStore
    ) -> None:
        assert (
            store.query_embeddings(
                namespaces=["nope"], account_name="junwin", query_vector=[1.0, 0.0, 0.0]
            )
            == []
        )

    def test_query_merges_namespaces(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(
            _record(record_id="a", namespace="documents", vector=[1.0, 0.0, 0.0])
        )
        store.upsert_embedding(
            _record(record_id="b", namespace="digests", vector=[0.0, 1.0, 0.0])
        )

        both = store.query_embeddings(
            namespaces=["documents", "digests"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert sorted(r.id for r, _ in both) == ["a", "b"]

        one = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert [r.id for r, _ in one] == ["a"]

    def test_query_filter_source_type(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(
            _record(record_id="dig", source_type="digest", vector=[1.0, 0.0, 0.0])
        )
        store.upsert_embedding(
            _record(record_id="doc", source_type="document", vector=[1.0, 0.0, 0.0])
        )

        filtered = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
            filter={"source_type": "digest"},
        )
        assert [r.id for r, _ in filtered] == ["dig"]

    def test_account_isolation(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(
            _record(record_id="mine", account="junwin", vector=[1.0, 0.0, 0.0])
        )
        store.upsert_embedding(
            _record(record_id="theirs", account="other", vector=[1.0, 0.0, 0.0])
        )

        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert [r.id for r, _ in results] == ["mine"]


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_delete_by_source_id(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(_record(record_id="a", source_id="sess-1"))
        store.upsert_embedding(_record(record_id="b", source_id="sess-2"))

        deleted = store.delete_embeddings(
            namespace="documents", account_name="junwin", source_id="sess-1"
        )
        assert deleted == 1

        remaining = store.query_embeddings(
            namespaces=["documents"], account_name="junwin", query_vector=[1.0, 0.0, 0.0]
        )
        assert [r.id for r, _ in remaining] == ["b"]

        # Idempotent: deleting again is a no-op returning 0.
        assert (
            store.delete_embeddings(
                namespace="documents", account_name="junwin", source_id="sess-1"
            )
            == 0
        )

    def test_delete_by_source_type(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(_record(record_id="a", source_type="digest"))
        store.upsert_embedding(_record(record_id="b", source_type="document"))

        deleted = store.delete_embeddings(
            namespace="documents", account_name="junwin", source_type="digest"
        )
        assert deleted == 1

        remaining = store.query_embeddings(
            namespaces=["documents"], account_name="junwin", query_vector=[1.0, 0.0, 0.0]
        )
        assert [r.id for r, _ in remaining] == ["b"]

    def test_delete_no_match_returns_zero(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(_record(record_id="a", source_id="sess-1"))
        assert (
            store.delete_embeddings(
                namespace="documents", account_name="junwin", source_id="missing"
            )
            == 0
        )

    def test_delete_missing_namespace_returns_zero(
        self, store: PrimitivesEmbeddingStore
    ) -> None:
        assert (
            store.delete_embeddings(
                namespace="nope", account_name="junwin", source_id="sess-1"
            )
            == 0
        )


# ---------------------------------------------------------------------------
# Namespace listing
# ---------------------------------------------------------------------------

class TestNamespaces:
    def test_list_namespaces_sorted(self, store: PrimitivesEmbeddingStore) -> None:
        store.upsert_embedding(_record(record_id="1", namespace="zeta"))
        store.upsert_embedding(_record(record_id="2", namespace="alpha"))
        store.upsert_embedding(_record(record_id="3", namespace="mid"))

        assert store.list_embedding_namespaces("junwin") == ["alpha", "mid", "zeta"]

    def test_list_namespaces_unknown_account(
        self, store: PrimitivesEmbeddingStore
    ) -> None:
        assert store.list_embedding_namespaces("nobody") == []

    def test_list_namespaces_ignores_other_accounts(
        self, store: PrimitivesEmbeddingStore
    ) -> None:
        store.upsert_embedding(
            _record(record_id="1", namespace="mine", account="junwin")
        )
        store.upsert_embedding(
            _record(record_id="2", namespace="theirs", account="other")
        )
        assert store.list_embedding_namespaces("junwin") == ["mine"]


# ---------------------------------------------------------------------------
# Persistence across backend reopen (file + sqlite)
# ---------------------------------------------------------------------------

PERSISTENT_FACTORIES = [
    pytest.param(_file_factory, id="file"),
    pytest.param(_sqlite_factory, id="sqlite"),
]


@pytest.mark.parametrize("factory", PERSISTENT_FACTORIES)
def test_reopen_persistence(
    factory: Callable[[Path], Any], tmp_path: Path
) -> None:
    backend = factory(tmp_path)
    store = PrimitivesEmbeddingStore(backend)
    store.upsert_embedding(_record(record_id="rec", vector=[1.0, 0.0, 0.0]))
    close = getattr(backend, "close", None)
    if callable(close):
        close()

    backend2 = factory(tmp_path)
    try:
        store2 = PrimitivesEmbeddingStore(backend2)
        results = store2.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert len(results) == 1
        assert results[0][0].id == "rec"
        assert results[0][1] == pytest.approx(1.0)
    finally:
        close2 = getattr(backend2, "close", None)
        if callable(close2):
            close2()


# ---------------------------------------------------------------------------
# Parity with the existing JsonFileStorage embedding store (file backend)
# ---------------------------------------------------------------------------

def test_parity_with_json_file_storage(tmp_path: Path) -> None:
    """The file backend writes the same physical files as EmbeddingsMixin,
    so the two implementations are interchangeable on disk."""
    storage_paths = StoragePaths(str(tmp_path / "root"), "data")
    jfs = JsonFileStorage(storage_paths)
    prim = PrimitivesEmbeddingStore(FileChat2Primitives(storage_paths.base))

    rec = _record(
        record_id="shared",
        namespace="documents",
        account="junwin",
        vector=[1.0, 0.0, 0.0],
        source_type="document",
        source_id="src-1",
        metadata={"path": "/tmp/note.md"},
    )

    # Write through JsonFileStorage (mixin), read through primitives store.
    jfs.upsert_embedding(rec)
    results = prim.query_embeddings(
        namespaces=["documents"],
        account_name="junwin",
        query_vector=[1.0, 0.0, 0.0],
    )
    assert len(results) == 1
    got, score = results[0]
    assert got.id == "shared"
    assert got.source_metadata == {"path": "/tmp/note.md"}
    assert score == pytest.approx(1.0)
    assert prim.list_embedding_namespaces("junwin") == ["documents"]

    # Write through primitives store, read through JsonFileStorage (mixin).
    prim.upsert_embedding(
        _record(
            record_id="from-prim",
            namespace="digests",
            account="junwin",
            vector=[0.0, 1.0, 0.0],
            source_type="digest",
            source_id="sess-9",
        )
    )
    jfs_results = jfs.query_embeddings(
        namespaces=["digests"],
        account_name="junwin",
        query_vector=[0.0, 1.0, 0.0],
    )
    assert len(jfs_results) == 1
    assert jfs_results[0][0].id == "from-prim"
    assert jfs_results[0][1] == pytest.approx(1.0)

    # Delete through the mixin must be seen by the primitives store and
    # vice versa (same underlying files).
    jfs.delete_embeddings(namespace="documents", account_name="junwin")
    assert (
        prim.query_embeddings(
            namespaces=["documents"], account_name="junwin", query_vector=[1.0, 0.0, 0.0]
        )
        == []
    )


# ---------------------------------------------------------------------------
# Factory (config-driven backend selection)
# ---------------------------------------------------------------------------

class _Cfg:
    """Minimal ConfigManager-like object with .get()."""

    def __init__(self, values: dict) -> None:
        self.values = values

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


def test_factory_defaults_to_file_backend(tmp_path: Path) -> None:
    store = build_primitives_embedding_store(
        _Cfg(
            {
                "storage_root_path": str(tmp_path / "root"),
                "storage_namespace": "data",
            }
        )
    )
    store.upsert_embedding(_record(record_id="r1", vector=[1.0, 0.0, 0.0]))

    # File backend writes the same layout as JsonFileStorage.
    expected = (
        tmp_path / "root" / "data" / "embeddings" / "junwin" / "documents" / "r1.json"
    )
    assert expected.exists()

    results = store.query_embeddings(
        namespaces=["documents"], account_name="junwin", query_vector=[1.0, 0.0, 0.0]
    )
    assert len(results) == 1


def test_factory_sqlite_backend(tmp_path: Path) -> None:
    db_path = tmp_path / "emb.sqlite"
    store = build_primitives_embedding_store(
        _Cfg(
            {
                "embedding_store_backend": "sqlite",
                "embedding_store_db_path": str(db_path),
            }
        )
    )
    try:
        store.upsert_embedding(_record(record_id="r1", vector=[1.0, 0.0, 0.0]))
        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert len(results) == 1
        assert results[0][1] == pytest.approx(1.0)
    finally:
        close = getattr(store._store, "close", None)
        if callable(close):
            close()

    # Data survives a reopen of the same db file.
    store2 = build_primitives_embedding_store(
        _Cfg(
            {
                "embedding_store_backend": "sqlite",
                "embedding_store_db_path": str(db_path),
            }
        )
    )
    try:
        results = store2.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert len(results) == 1
    finally:
        close = getattr(store2._store, "close", None)
        if callable(close):
            close()
