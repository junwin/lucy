"""Concurrency regression tests for the v1 chat session storage.

These tests document the races behind the "2 client sessions" concern:

1. ``create_chat_session`` does a read-modify-write on ``index.json`` with no
   synchronization, so concurrent creates can lose index entries — a session
   file is written to disk but becomes unfindable via ``get_chat_session`` /
   ``list_chat_sessions``.

2. The ``/ask`` session-resolution path does check-then-act
   (``find_chat_sessions_by_friendly_name`` then ``create_chat_session``) with
   no uniqueness guard, so two concurrent requests carrying the same
   ``friendlyName`` each create a separate session.

3. ``JsonFileStorage._atomic_write`` uses a *fixed* tmp path
   (``<target>.tmp``), so two threads writing the same target concurrently
   collide on the tmp file and one write crashes/clobbers.

The storage layer now serializes chat writes with a per-instance ``RLock`` and
exposes an atomic ``get_or_create_chat_session``. These tests assert the
correct behavior and pass once the storage layer is concurrency-safe.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from src.storage.json_file_storage import JsonFileStorage
from src.storage_paths.storage_paths import StoragePaths


def _make_storage(tmp_path: Path) -> JsonFileStorage:
    """Create a real JsonFileStorage backed by a temp directory."""
    return JsonFileStorage(StoragePaths(str(tmp_path), "test_ns"))


def _run_threads(n: int, target) -> None:
    """Start ``n`` threads running ``target`` and join them all."""
    threads = [threading.Thread(target=target) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def _read_index(storage: JsonFileStorage, account_name: str) -> dict:
    """Read index.json directly, bypassing any monkeypatched ``_load_json``."""
    index_path = storage.storage_paths.chats / account_name / "index.json"
    if not index_path.exists():
        return {}
    return json.loads(index_path.read_text(encoding="utf-8"))


def test_concurrent_create_chat_session_preserves_all_index_entries(
    tmp_path,
):
    """Two concurrent creates must both remain discoverable."""

    storage = _make_storage(tmp_path)

    n = 2
    created_ids: list[str] = []
    ids_lock = threading.Lock()

    def create():
        session = storage.create_chat_session("acct", "lucy", friendly_name="dup")
        with ids_lock:
            created_ids.append(session.id)

    _run_threads(n, create)

    chat_dir = storage.storage_paths.chats / "acct"
    session_files = sorted(
        p.name for p in chat_dir.glob("*.json") if p.name != "index.json"
    )
    index = _read_index(storage, "acct")

    assert len(session_files) == n
    assert set(index.keys()) == set(created_ids)


def test_concurrent_get_or_create_reuses_single_session(tmp_path):
    """Two concurrent /ask-style resolutions must share one session."""

    storage = _make_storage(tmp_path)

    n = 2
    resolved_ids: list[str] = []
    created_flags: list[bool] = []
    results_lock = threading.Lock()

    def resolve():
        session, created = storage.get_or_create_chat_session("acct", "lucy", "dup")
        with results_lock:
            resolved_ids.append(session.id)
            created_flags.append(created)

    _run_threads(n, resolve)

    assert len(set(resolved_ids)) == 1
    assert sorted(created_flags) == [False, True]


def test_concurrent_atomic_write_tmp_path_collision(tmp_path, monkeypatch):
    """Document the separate tmp-path collision in ``_atomic_write``.

    Two threads writing the same target both use ``<target>.tmp``, so the
    second writer's ``shutil.move`` fails once the first has moved the tmp file
    away. This test fails when that collision is present (one writer errors).
    """
    storage = _make_storage(tmp_path)

    n = 2
    barrier = threading.Barrier(n)
    original_replace = storage._atomic_replace
    errors: list[Exception] = []

    def coordinated_replace(tmp_path, target_path):
        # Both threads have already written the SAME tmp file by this point.
        barrier.wait(timeout=5)
        try:
            return original_replace(tmp_path, target_path)
        except Exception as exc:  # noqa: BLE001 - documenting the collision
            errors.append(exc)

    monkeypatch.setattr(storage, "_atomic_replace", coordinated_replace)

    target = storage.storage_paths.base / "shared.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    def write():
        storage._atomic_write(target, {"thread": threading.get_ident()})

    _run_threads(n, write)

    assert errors == []
