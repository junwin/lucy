"""DI wiring tests for the optional embedding store backend selection.

Covers ``StorageModule.provide_embedding_store``: the default wiring (shared
JsonFileStorage) stays untouched, ``embedding_store_backend=file`` / ``sqlite``
opt into ``PrimitivesEmbeddingStore``, and an unknown value fails loudly.
"""

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.container_config import StorageModule
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import PrimitivesEmbeddingStore
from tests.conftest import FakeConfig

import pytest


def _storage_module(monkeypatch, values: dict) -> StorageModule:
    """Build a StorageModule whose module-level config is a FakeConfig."""
    import src.container_config as cc

    monkeypatch.setattr(cc, "config", FakeConfig(values))
    return cc.StorageModule()


def _sentinel_storage():
    """A dummy Storage object; only identity matters for these tests."""
    return object()


def _record(record_id: str) -> EmbeddingRecord:
    return EmbeddingRecord(
        id=record_id,
        namespace="documents",
        account_name="junwin",
        vector=[1.0, 0.0, 0.0],
        source_type="note",
        source_id="src1",
        source_metadata={},
    )


# ---------------------------------------------------------------------------
# Default wiring
# ---------------------------------------------------------------------------


def test_embedding_store_defaults_to_shared_storage(monkeypatch):
    """Unset backend -> the same JsonFileStorage instance is returned."""
    module = _storage_module(monkeypatch, {})
    storage = _sentinel_storage()
    assert module.provide_embedding_store(storage) is storage


def test_embedding_store_empty_backend_keeps_shared_storage(monkeypatch):
    module = _storage_module(monkeypatch, {"embedding_store_backend": ""})
    storage = _sentinel_storage()
    assert module.provide_embedding_store(storage) is storage


# ---------------------------------------------------------------------------
# file backend
# ---------------------------------------------------------------------------


def test_embedding_store_file_backend(monkeypatch, tmp_path):
    module = _storage_module(
        monkeypatch,
        {
            "embedding_store_backend": "file",
            "storage_root_path": str(tmp_path / "root"),
            "storage_namespace": "data",
        },
    )
    storage = _sentinel_storage()
    store = module.provide_embedding_store(storage)

    assert isinstance(store, PrimitivesEmbeddingStore)
    assert isinstance(store._store, FileChat2Primitives)
    assert store is not storage

    # Same on-disk layout as JsonFileStorage.
    store.upsert_embedding(_record(record_id="r1"))
    expected = (
        tmp_path / "root" / "data" / "embeddings" / "junwin" / "documents" / "r1.json"
    )
    assert expected.exists()


def test_embedding_store_file_backend_uppercase(monkeypatch, tmp_path):
    """Backend value is normalized (case-insensitive)."""
    module = _storage_module(
        monkeypatch,
        {
            "embedding_store_backend": "File",
            "storage_root_path": str(tmp_path / "root"),
            "storage_namespace": "data",
        },
    )
    store = module.provide_embedding_store(_sentinel_storage())
    assert isinstance(store._store, FileChat2Primitives)


# ---------------------------------------------------------------------------
# sqlite backend
# ---------------------------------------------------------------------------


def test_embedding_store_sqlite_backend(monkeypatch, tmp_path):
    db_path = tmp_path / "emb.sqlite"
    module = _storage_module(
        monkeypatch,
        {
            "embedding_store_backend": "sqlite",
            "embedding_store_db_path": str(db_path),
        },
    )
    store = module.provide_embedding_store(_sentinel_storage())

    assert isinstance(store, PrimitivesEmbeddingStore)
    assert isinstance(store._store, SqliteChat2Primitives)

    try:
        store.upsert_embedding(_record(record_id="r1"))
        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0, 0.0, 0.0],
        )
        assert len(results) == 1
    finally:
        store._store.close()

    assert db_path.exists()


def test_embedding_store_sqlite_default_db_path(monkeypatch, tmp_path):
    """No explicit db path -> <storage_root>/<namespace>/embeddings.sqlite."""
    # In production the storage namespace dir already exists (JsonFileStorage
    # creates it); mirror that here since SqliteChat2Primitives does not mkdir.
    (tmp_path / "root" / "data").mkdir(parents=True)
    module = _storage_module(
        monkeypatch,
        {
            "embedding_store_backend": "sqlite",
            "storage_root_path": str(tmp_path / "root"),
            "storage_namespace": "data",
        },
    )
    store = module.provide_embedding_store(_sentinel_storage())
    expected = tmp_path / "root" / "data" / "embeddings.sqlite"
    try:
        store.upsert_embedding(_record(record_id="r1"))
        assert expected.exists()
    finally:
        store._store.close()


# ---------------------------------------------------------------------------
# Unknown backend fails loudly
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["sqllite", "mongo", "file!"])
def test_embedding_store_unknown_backend_raises(monkeypatch, bad):
    module = _storage_module(monkeypatch, {"embedding_store_backend": bad})
    with pytest.raises(ValueError, match="embedding_store_backend"):
        module.provide_embedding_store(_sentinel_storage())
