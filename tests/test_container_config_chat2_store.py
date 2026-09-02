from src.chat2.adapters.jfs_adapter import JfsChat2Primitives
from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent
from src.chat2.sqlite import SqliteChat2Primitives
from src.container_config import StorageModule
from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths
from tests.conftest import FakeConfig

import pytest


def _storage_module(monkeypatch, values):
    import src.container_config as cc

    monkeypatch.setattr(cc, "config", FakeConfig(values))
    return cc.StorageModule()


def _sentinel_storage():
    return object()


def _json_storage(tmp_path):
    paths = StoragePaths(
        storage_root_path=str(tmp_path / "root"),
        storage_namespace="data",
    )
    return JsonFileStorage(paths)


def _event():
    return ChatEvent(
        role="user",
        actor="junwin",
        kind="user_message",
        payload="hello",
    )


def test_chat2_store_defaults_to_jfs_adapter(monkeypatch, tmp_path):
    module = _storage_module(monkeypatch, {})
    storage = _json_storage(tmp_path)
    store = module.provide_chat2_store(storage)
    assert isinstance(store, Chat2Store)
    assert isinstance(store._store, JfsChat2Primitives)
    assert store._store._storage is storage


def test_chat2_store_empty_backend_keeps_jfs_adapter(monkeypatch, tmp_path):
    module = _storage_module(monkeypatch, {"chat2_store_backend": ""})
    storage = _json_storage(tmp_path)
    store = module.provide_chat2_store(storage)
    assert isinstance(store._store, JfsChat2Primitives)
    assert store._store._storage is storage


def test_chat2_store_jsonl_backend(monkeypatch, tmp_path):
    module = _storage_module(monkeypatch, {"chat2_store_backend": "jsonl"})
    storage = _json_storage(tmp_path)
    store = module.provide_chat2_store(storage)
    assert isinstance(store, Chat2Store)
    assert isinstance(store._store, JfsChat2Primitives)
    assert store._store._storage is storage


def test_chat2_store_jsonl_backend_uppercase(monkeypatch, tmp_path):
    module = _storage_module(monkeypatch, {"chat2_store_backend": "JSONL"})
    storage = _json_storage(tmp_path)
    store = module.provide_chat2_store(storage)
    assert isinstance(store._store, JfsChat2Primitives)


def test_chat2_store_sqlite_backend(monkeypatch, tmp_path):
    db_path = tmp_path / "chat2.sqlite"
    module = _storage_module(
        monkeypatch,
        {
            "chat2_store_backend": "sqlite",
            "chat2_store_db_path": str(db_path),
        },
    )
    store = module.provide_chat2_store(_sentinel_storage())
    assert isinstance(store, Chat2Store)
    assert isinstance(store._store, SqliteChat2Primitives)
    try:
        meta = store.create_session(
            user_id="user1",
            account_name="junwin",
            agent_name="lucy",
        )
        store.add_event(meta.session_id, _event())
        streamed = list(store.stream_events(meta.session_id))
        sessions = store.list_sessions(account_name="junwin")
        assert len(streamed) == 1
        assert streamed[0].payload == "hello"
        assert [s.session_id for s in sessions] == [meta.session_id]
    finally:
        store._store.close()
    assert db_path.exists()


def test_chat2_store_sqlite_default_db_path(monkeypatch, tmp_path):
    (tmp_path / "root" / "data").mkdir(parents=True)
    module = _storage_module(
        monkeypatch,
        {
            "chat2_store_backend": "sqlite",
            "storage_root_path": str(tmp_path / "root"),
            "storage_namespace": "data",
        },
    )
    store = module.provide_chat2_store(_sentinel_storage())
    expected = tmp_path / "root" / "data" / "chat2.sqlite"
    try:
        meta = store.create_session(
            user_id="user1",
            account_name="junwin",
            agent_name="lucy",
        )
        store.add_event(meta.session_id, _event())
        assert expected.exists()
    finally:
        store._store.close()


@pytest.mark.parametrize("bad", ["sqllite", "mongo", "file!"])
def test_chat2_store_unknown_backend_raises(monkeypatch, bad):
    module = _storage_module(monkeypatch, {"chat2_store_backend": bad})
    with pytest.raises(ValueError, match="chat2_store_backend"):
        module.provide_chat2_store(_sentinel_storage())
