"""DI wiring tests for Lucy embedding-store configuration.

The default wiring (shared JsonFileStorage) stays untouched. Explicit ``file``
and ``sqlite`` backends use ``PrimitivesEmbeddingStore``. ``sqlite_vec`` is a
supported Lucy configuration choice but delegates native vector storage to
``galet-memory`` through the compatibility adapter.
"""

import pytest

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.container_config import StorageModule
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import PrimitivesEmbeddingStore
from tests.conftest import FakeConfig


def _storage_module(monkeypatch, values: dict) -> StorageModule:
    import src.container_config as cc

    monkeypatch.setattr(cc, "config", FakeConfig(values))
    return cc.StorageModule()


def _sentinel_storage():
    return object()


def _record(record_id: str, dimensions: int = 3) -> EmbeddingRecord:
    vector = [0.0] * dimensions
    vector[0] = 1.0
    return EmbeddingRecord(
        id=record_id,
        namespace="documents",
        account_name="junwin",
        vector=vector,
        source_type="note",
        source_id="src1",
        source_metadata={},
    )


def test_embedding_store_defaults_to_shared_storage(monkeypatch):
    module = _storage_module(monkeypatch, {})
    storage = _sentinel_storage()
    assert module.provide_embedding_store(storage) is storage


def test_embedding_store_empty_backend_keeps_shared_storage(monkeypatch):
    module = _storage_module(monkeypatch, {"embedding_store_backend": ""})
    storage = _sentinel_storage()
    assert module.provide_embedding_store(storage) is storage


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

    store.upsert_embedding(_record(record_id="r1"))
    expected = (
        tmp_path
        / "root"
        / "data"
        / "embeddings"
        / "junwin"
        / "documents"
        / "r1.json"
    )
    assert expected.exists()


def test_embedding_store_file_backend_uppercase(monkeypatch, tmp_path):
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
    expected = tmp_path / "root" / "data" / "embeddings-v2.sqlite"
    try:
        store.upsert_embedding(_record(record_id="r1"))
        assert expected.exists()
    finally:
        store._store.close()


def test_embedding_store_sqlite_vec_delegates_to_galet_memory(monkeypatch, tmp_path):
    pytest.importorskip("sqlite_vec")
    from src.storage.vec0_embedding_store import Vec0EmbeddingStore

    db_path = tmp_path / "emb_vec0.sqlite"
    module = _storage_module(
        monkeypatch,
        {
            "embedding_store_backend": "sqlite_vec",
            "embedding_store_db_path": str(db_path),
        },
    )
    store = module.provide_embedding_store(_sentinel_storage())
    assert isinstance(store, Vec0EmbeddingStore)
    try:
        store.upsert_embedding(_record("r1", dimensions=1536))
        results = store.query_embeddings(
            namespaces=["documents"],
            account_name="junwin",
            query_vector=[1.0] + [0.0] * 1535,
            top_k=1,
        )
        assert results
        assert results[0][0].id == "r1"
    finally:
        store.close()
    assert db_path.exists()


@pytest.mark.parametrize("bad", ["sqllite", "mongo", "file!"])
def test_embedding_store_unknown_backend_raises(monkeypatch, bad):
    module = _storage_module(monkeypatch, {"embedding_store_backend": bad})
    with pytest.raises(ValueError, match="embedding_store_backend"):
        module.provide_embedding_store(_sentinel_storage())
