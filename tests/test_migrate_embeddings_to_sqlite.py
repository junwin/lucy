"""Tests for the file-to-sqlite embedding migration script.

Covers ``migrate_embeddings_to_sqlite.migrate_embeddings``: keys under the
``embeddings/`` prefix are copied verbatim, malformed/stray keys are skipped,
re-running is idempotent, and dry-run writes nothing.
"""

from __future__ import annotations

from pathlib import Path

from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import StoreKey

from scripts.migrate_embeddings_to_sqlite import migrate_embeddings


def _make_file_store(root: Path, records: dict[str, str]) -> FileChat2Primitives:
    """Write embedding-like JSON docs under root/embeddings/<account>/<ns>/."""
    store = FileChat2Primitives(root)
    for key, text in records.items():
        store.write_text(StoreKey(key), text)
    return store


def test_migrate_copies_verbatim_and_skips_stray(tmp_path):
    records = {
        "embeddings/junwin/documents/d1.json": '{"id": "d1", "vector": [0.1]}',
        "embeddings/junwin/vol_5/v5.json": '{"id": "v5", "vector": [0.2, 0.3]}',
        "embeddings/alice/books/b1.json": '{"id": "b1", "vector": [1.0]}',
        "embeddings/stray.json": "{}",  # not <account>/<namespace>/<id>.json
    }
    file_store = _make_file_store(tmp_path, records)
    sqlite_store = SqliteChat2Primitives(str(tmp_path / "embeddings.sqlite"))
    try:
        total, copied, skipped = migrate_embeddings(file_store, sqlite_store)

        assert total == 4
        assert copied == 3
        assert skipped == ["embeddings/stray.json"]

        keys = sqlite_store.list_keys(StoreKey("embeddings/"))
        assert len(keys) == 3
        for key in keys:
            assert sqlite_store.read_text(key) == file_store.read_text(key)
    finally:
        sqlite_store.close()


def test_migrate_is_idempotent(tmp_path):
    records = {"embeddings/junwin/documents/d1.json": '{"id": "d1", "vector": [0.1]}'}
    file_store = _make_file_store(tmp_path, records)
    sqlite_store = SqliteChat2Primitives(str(tmp_path / "embeddings.sqlite"))
    try:
        migrate_embeddings(file_store, sqlite_store)
        migrate_embeddings(file_store, sqlite_store)
        assert len(sqlite_store.list_keys(StoreKey("embeddings/"))) == 1
    finally:
        sqlite_store.close()


def test_migrate_dry_run_writes_nothing(tmp_path):
    records = {"embeddings/junwin/documents/d1.json": '{"id": "d1", "vector": [0.1]}'}
    file_store = _make_file_store(tmp_path, records)
    sqlite_store = SqliteChat2Primitives(str(tmp_path / "embeddings.sqlite"))
    try:
        total, copied, skipped = migrate_embeddings(
            file_store, sqlite_store, dry_run=True
        )
        assert total == 1
        assert copied == 1
        assert skipped == []
        assert sqlite_store.list_keys(StoreKey("embeddings/")) == []
    finally:
        sqlite_store.close()


def test_migrate_overwrites_existing_sqlite_values(tmp_path):
    records = {"embeddings/junwin/documents/d1.json": '{"id": "d1", "vector": [0.1]}'}
    file_store = _make_file_store(tmp_path, records)
    sqlite_store = SqliteChat2Primitives(str(tmp_path / "embeddings.sqlite"))
    try:
        # Pre-existing older value at the same key.
        sqlite_store.write_text(
            StoreKey("embeddings/junwin/documents/d1.json"), '{"old": true}'
        )
        migrate_embeddings(file_store, sqlite_store)
        assert (
            sqlite_store.read_text(StoreKey("embeddings/junwin/documents/d1.json"))
            == '{"id": "d1", "vector": [0.1]}'
        )
    finally:
        sqlite_store.close()
