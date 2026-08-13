"""Concurrency reproduction tests for the v1 chat session storage.

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

Tests 1 and 2 are made deterministic with ``threading.Barrier``. They assert the
*correct* behavior, so they are EXPECTED TO FAIL until the storage layer is
made concurrency-safe (issue step 3).
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


def _serialize_writes(storage: JsonFileStorage, monkeypatch) -> None:
    """Wrap ``_atomic_write`` so concurrent writes do not collide on the
    shared ``<target>.tmp`` path.

    This isolates the read-modify-write bug (test 1) and the check-then-act
    bug (test 2) from the separate tmp-path collision bug (test 3).
    """
    lock = threading.Lock()
    original = storage._atomic_write

    def locked_write(path, data):
        with lock:
            return original(path, data)

    monkeypatch.setattr(storage, "_atomic_write", locked_write)


def _read_index(storage: JsonFileStorage, account_name: str) -> dict:
    """Read index.json directly, bypassing any monkeypatched ``_load_json``."""
    index_path = storage.storage_paths.chats / account_name / "index.json"
    if not index_path.exists():
        return {}
    return json.loads(index_path.read_text(encoding="utf-8"))


def test_concurrent_create_chat_session_preserves_all_index_entries(
    tmp_path, monkeypatch
):
    """Two concurrent creates must both remain discoverable.

    Today this FAILS: the index.json read-modify-write is unsynchronized, so
    the second writer overwrites the first writer's entry even though both
    session files exist on disk.
    """
    storage = _make_storage(tmp_path)
    _serialize_writes(storage, monkeypatch)

    n = 2
    read_barrier = threading.Barrier(n)
    original_load = storage._load_json

    def coordinated_load(path):
        data = original_load(path)
        # Both threads have now read the (empty) index snapshot; release them
        # together so each proceeds to write its stale copy.
        if path.name == "index.json":
            read_barrier.wait(timeout=5)
        return data

    monkeypatch.setattr(storage, "_load_json", coordinated_load)

    created_ids: list[str] = []

    def create():
        session = storage.create_chat_session("acct", "lucy", friendly_name="dup")
        created_ids.append(session.id)

    _run_threads(n, create)

    chat_dir = storage.storage_paths.chats / "acct"
    session_files = sorted(
        p.name for p in chat_dir.glob("*.json") if p.name != "index.json"
    )
    index = _read_index(storage, "acct")

    # Both session files exist on disk...
    assert len(session_files) == n
    # ...but the index must also contain both entries. Fails today: one is lost.
    assert set(index.keys()) == set(created_ids)


def test_concurrent_find_then_create_reuses_single_session(tmp_path, monkeypatch):
    """Two concurrent /ask-style resolutions must share one session.

    Mirrors the check-then-act the handler performs: find by friendly name, and
    only create when no match is found. Today this FAILS: both threads see "no
    match" and each creates a separate session with the same friendly name.
    """
    storage = _make_storage(tmp_path)
    _serialize_writes(storage, monkeypatch)

    n = 2
    barrier = threading.Barrier(n)
    resolved_ids: list[str] = []

    def resolve():
        matches = storage.find_chat_sessions_by_friendly_name(
            "acct", "lucy", "dup", limit=1
        )
        if matches:
            resolved_ids.append(matches[0].id)
            return
        # Widen the check-then-act window so both threads observe "no match"
        # before either one creates.
        barrier.wait(timeout=5)
        session = storage.create_chat_session("acct", "lucy", friendly_name="dup")
        resolved_ids.append(session.id)

    _run_threads(n, resolve)

    # Correct behavior: both requests resolve to one shared session.
    # Fails today: two distinct session ids.
    assert len(set(resolved_ids)) == 1


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

    # Correct behavior: both writers succeed (no shared tmp path). Today this
    # FAILS because one writer raises FileNotFoundError after the tmp file is
    # moved by the other.
    assert errors == []
