"""Sync-semantics tests for the embedding namespace sync (issue #149).

Covers the F6 store surface (``list_embeddings``, delete by record id) and
the shared sync semantics (sha256 content-hash skip, re-embed on change,
namespace-scoped prune by record id) on every embedding backend — file,
sqlite and vec0. vec0 instances skip gracefully when the sqlite-vec
extension is unavailable. Dry runs must never write.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from scripts.embed_digests import sync_digests
from scripts.embed_external import sync_directory
from scripts.embed_sync import prune_missing, sha256_file
from src.chat2.fs_primitives import FileChat2Primitives
from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import InMemoryStore
from src.storage.json_file_storage import JsonFileStorage
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import PrimitivesEmbeddingStore
from src.storage.vec0_embedding_store import (
    DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    Vec0EmbeddingStore,
)
from src.storage_paths.storage_paths import StoragePaths

_DIM = 1536
_SILENT = lambda _message: None


def _vector(index: int = 0) -> List[float]:
    vector = [0.0] * _DIM
    vector[index % _DIM] = 1.0
    return vector


def _require_vec0() -> None:
    if not Path(DEFAULT_SQLITE_VEC_EXTENSION_PATH).exists():
        pytest.skip("sqlite-vec extension not available")
    conn = sqlite3.connect(":memory:")
    try:
        conn.enable_load_extension(True)
        conn.load_extension(DEFAULT_SQLITE_VEC_EXTENSION_PATH)
    except sqlite3.OperationalError:
        pytest.skip("sqlite-vec extension not loadable")
    finally:
        conn.close()


@pytest.fixture(
    params=[
        pytest.param("memory", id="memory"),
        pytest.param("file", id="file"),
        pytest.param("sqlite", id="sqlite"),
        pytest.param("vec0", id="vec0"),
    ]
)
def embedding_store(request: pytest.FixtureRequest, tmp_path: Path) -> Any:
    kind: str = request.param
    if kind == "memory":
        store: Any = PrimitivesEmbeddingStore(InMemoryStore())
    elif kind == "file":
        store = PrimitivesEmbeddingStore(FileChat2Primitives(tmp_path / "fs"))
    elif kind == "sqlite":
        store = PrimitivesEmbeddingStore(SqliteChat2Primitives(tmp_path / "store.db"))
    else:
        _require_vec0()
        store = Vec0EmbeddingStore(str(tmp_path / "vec0.sqlite"))
    yield store
    close = getattr(store, "close", None)
    if callable(close):
        close()


def _record(
    record_id: str,
    namespace: str = "documents",
    *,
    account: str = "junwin",
    source_type: str = "document",
    source_id: str = "src-1",
    metadata: Optional[Dict[str, Any]] = None,
    path: Optional[Path] = None,
    relative_path: Optional[str] = None,
    content_hash: Optional[str] = None,
    vector: Optional[List[float]] = None,
) -> EmbeddingRecord:
    meta: Dict[str, Any] = dict(metadata or {})
    if path is not None:
        meta["path"] = str(path)
    if relative_path is not None:
        meta["relative_path"] = relative_path
    if content_hash is not None:
        meta["content_hash"] = content_hash
    return EmbeddingRecord(
        id=record_id,
        namespace=namespace,
        account_name=account,
        vector=vector if vector is not None else _vector(),
        source_type=source_type,
        source_id=source_id,
        source_metadata=meta,
    )


def _ids(store: Any, namespace: str = "documents", account: str = "junwin") -> List[str]:
    return [record.id for record in store.list_embeddings(namespace, account)]


def _write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# F6 surface: list_embeddings + delete by record id
# ---------------------------------------------------------------------------


class TestStoreListDelete:
    def test_list_embeddings_sorted_roundtrip(self, embedding_store: Any) -> None:
        embedding_store.upsert_embedding(
            _record("zebra", metadata={"path": "/tmp/z.md"}, content_hash=None)
        )
        embedding_store.upsert_embedding(
            _record(
                "alpha",
                source_type="digest",
                source_id="sess-1",
                metadata={"path": "/tmp/a.md", "content_hash": "abc123"},
            )
        )
        embedding_store.upsert_embedding(_record("mid"))

        records = embedding_store.list_embeddings("documents", "junwin")
        assert [record.id for record in records] == ["alpha", "mid", "zebra"]
        alpha = records[0]
        assert alpha.source_type == "digest"
        assert alpha.source_id == "sess-1"
        assert alpha.source_metadata == {"path": "/tmp/a.md", "content_hash": "abc123"}
        assert len(alpha.vector) == _DIM
        assert alpha.created_at is not None

    def test_list_embeddings_empty_for_unknown_scope(self, embedding_store: Any) -> None:
        embedding_store.upsert_embedding(_record("r1"))
        assert embedding_store.list_embeddings("missing", "junwin") == []
        assert embedding_store.list_embeddings("documents", "nobody") == []

    def test_delete_by_record_id_exact(self, embedding_store: Any) -> None:
        embedding_store.upsert_embedding(_record("a", source_id="sess-1"))
        embedding_store.upsert_embedding(_record("b", source_id="sess-2"))

        assert (
            embedding_store.delete_embeddings(
                "documents", "junwin", record_id="a"
            )
            == 1
        )
        assert _ids(embedding_store) == ["b"]
        assert (
            embedding_store.delete_embeddings(
                "documents", "junwin", record_id="a"
            )
            == 0
        )

    def test_delete_by_record_id_never_expands_shared_source_id(
        self, embedding_store: Any
    ) -> None:
        embedding_store.upsert_embedding(
            _record("sess-1_a", namespace="digests", source_id="sess-1")
        )
        embedding_store.upsert_embedding(
            _record("sess-1_b", namespace="digests", source_id="sess-1")
        )

        assert (
            embedding_store.delete_embeddings(
                "digests", "junwin", record_id="sess-1_a"
            )
            == 1
        )
        remaining = embedding_store.list_embeddings("digests", "junwin")
        assert [record.id for record in remaining] == ["sess-1_b"]
        assert remaining[0].source_id == "sess-1"


# ---------------------------------------------------------------------------
# JsonFileStorage (EmbeddingsMixin) surface
# ---------------------------------------------------------------------------


class TestJsonFileStorageSurface:
    def test_list_and_delete_by_record_id_interop(self, tmp_path: Path) -> None:
        storage_paths = StoragePaths(str(tmp_path / "root"), "data")
        jfs = JsonFileStorage(storage_paths)
        prim = PrimitivesEmbeddingStore(FileChat2Primitives(storage_paths.base))

        jfs.upsert_embedding(_record("r1", path=tmp_path / "root" / "a.md"))
        jfs.upsert_embedding(_record("r2", path=tmp_path / "root" / "b.md"))

        listed = jfs.list_embeddings("documents", "junwin")
        assert [record.id for record in listed] == ["r1", "r2"]
        assert listed[0].source_metadata["path"].endswith("a.md")

        assert jfs.delete_embeddings("documents", "junwin", record_id="r1") == 1
        assert [record.id for record in prim.list_embeddings("documents", "junwin")] == [
            "r2"
        ]

        assert prim.delete_embeddings("documents", "junwin", record_id="r2") == 1
        assert jfs.list_embeddings("documents", "junwin") == []

    def test_list_embeddings_empty_when_namespace_missing(self, tmp_path: Path) -> None:
        jfs = JsonFileStorage(StoragePaths(str(tmp_path / "root"), "data"))
        assert jfs.list_embeddings("documents", "junwin") == []


# ---------------------------------------------------------------------------
# Shared prune semantics
# ---------------------------------------------------------------------------


class TestPruneMissing:
    def test_prune_missing_scoped_by_root_namespace_and_account(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        root = tmp_path / "corpus"
        _write_md(root / "keep" / "a.md", "alpha")
        outside = tmp_path / "elsewhere" / "x.md"

        embedding_store.upsert_embedding(
            _record("a", path=root / "keep" / "a.md")
        )
        embedding_store.upsert_embedding(_record("b", path=root / "gone.md"))
        embedding_store.upsert_embedding(
            _record("c", path=outside, namespace="documents")
        )
        embedding_store.upsert_embedding(
            _record("d", relative_path="rel_gone.md")
        )
        embedding_store.upsert_embedding(
            _record("other-ns", namespace="books", path=root / "gone.md")
        )
        embedding_store.upsert_embedding(
            _record("other-account", account="alice", path=root / "gone.md")
        )

        removed = prune_missing(
            embedding_store,
            account_name="junwin",
            namespace="documents",
            source_root=root,
            log=_SILENT,
        )
        assert removed == ["b", "d"]
        assert _ids(embedding_store) == ["a", "c"]
        assert _ids(embedding_store, namespace="books") == ["other-ns"]
        assert _ids(embedding_store, account="alice") == ["other-account"]

    def test_prune_dry_run_writes_nothing(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        root = tmp_path / "corpus"
        _write_md(root / "a.md", "alpha")
        embedding_store.upsert_embedding(_record("a", path=root / "a.md"))
        embedding_store.upsert_embedding(_record("zombie", path=root / "zombie.md"))

        removed = prune_missing(
            embedding_store,
            account_name="junwin",
            namespace="documents",
            source_root=root,
            dry_run=True,
            log=_SILENT,
        )
        assert removed == ["zombie"]
        assert _ids(embedding_store) == ["a", "zombie"]

    def test_prune_digests_shared_session_keeps_survivor(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        digests_dir = tmp_path / "digests"
        _write_md(digests_dir / "sess-1_b.md", "beta digest text")
        embedding_store.upsert_embedding(
            _record(
                "sess-1_a",
                namespace="digests",
                source_type="digest",
                source_id="sess-1",
                path=digests_dir / "sess-1_a.md",
            )
        )
        embedding_store.upsert_embedding(
            _record(
                "sess-1_b",
                namespace="digests",
                source_type="digest",
                source_id="sess-1",
                path=digests_dir / "sess-1_b.md",
            )
        )

        removed = prune_missing(
            embedding_store,
            account_name="junwin",
            namespace="digests",
            source_root=digests_dir,
            log=_SILENT,
        )
        assert removed == ["sess-1_a"]
        remaining = embedding_store.list_embeddings("digests", "junwin")
        assert [record.id for record in remaining] == ["sess-1_b"]
        assert remaining[0].source_id == "sess-1"


# ---------------------------------------------------------------------------
# embed_external sync loop
# ---------------------------------------------------------------------------


def _run_external(
    store: Any,
    source_dir: Path,
    md_files: List[Path],
    **kwargs: Any,
) -> Dict[str, int]:
    return sync_directory(
        store=store,
        account="junwin",
        namespace="documents",
        source_type="document",
        source_dir=source_dir,
        md_files=md_files,
        embed_fn=lambda text: _vector(len(text) % _DIM),
        log=_SILENT,
        **kwargs,
    )


class TestExternalSync:
    def test_first_run_embeds_all_with_content_hash(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "docs"
        _write_md(source_dir / "a.md", "alpha " * 40)
        _write_md(source_dir / "b.md", "beta " * 40)
        files = sorted(source_dir.glob("*.md"))

        counts = _run_external(embedding_store, source_dir, files)
        assert counts == {
            "embedded": 2,
            "skipped": 0,
            "skipped_empty": 0,
            "pruned": 0,
            "errors": 0,
        }

        by_id = {
            record.id: record
            for record in embedding_store.list_embeddings("documents", "junwin")
        }
        assert set(by_id) == {"a", "b"}
        for md_file in files:
            record = by_id[md_file.stem]
            assert record.source_metadata["content_hash"] == sha256_file(md_file)
            assert record.source_metadata["path"] == str(md_file)
            assert record.source_metadata["relative_path"] == md_file.name

    def test_skip_unchanged_reembed_changed_prune_missing(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "docs"
        for name in ("a", "b", "c", "d"):
            _write_md(source_dir / f"{name}.md", f"{name} content " * 40)
        all_files = sorted(source_dir.glob("*.md"))

        first = _run_external(embedding_store, source_dir, all_files)
        assert first["embedded"] == 4
        assert first["pruned"] == 0

        _write_md(source_dir / "b.md", "beta changed " * 40)
        (source_dir / "c.md").unlink()
        remaining = sorted(source_dir.glob("*.md"))

        second = _run_external(embedding_store, source_dir, remaining)
        assert second["embedded"] == 1
        assert second["skipped"] == 2
        assert second["pruned"] == 1

        by_id = {
            record.id: record
            for record in embedding_store.list_embeddings("documents", "junwin")
        }
        assert set(by_id) == {"a", "b", "d"}
        assert by_id["b"].source_metadata["content_hash"] == sha256_file(
            source_dir / "b.md"
        )

        third = _run_external(embedding_store, source_dir, remaining)
        assert third["embedded"] == 0
        assert third["skipped"] == 3
        assert third["pruned"] == 0
        assert len(_ids(embedding_store)) == 3

    def test_dry_run_writes_nothing(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "docs"
        _write_md(source_dir / "a.md", "alpha " * 40)
        _write_md(source_dir / "b.md", "beta " * 40)
        _run_external(
            embedding_store,
            source_dir,
            sorted(source_dir.glob("*.md")),
        )

        (source_dir / "a.md").unlink()
        _write_md(source_dir / "c.md", "gamma " * 40)
        files = sorted(source_dir.glob("*.md"))

        dry = _run_external(
            embedding_store,
            source_dir,
            files,
            dry_run=True,
        )
        assert dry["embedded"] == 1
        assert dry["skipped"] == 1
        assert dry["pruned"] == 1
        assert _ids(embedding_store) == ["a", "b"]

        real = _run_external(embedding_store, source_dir, files)
        assert real["embedded"] == 1
        assert real["pruned"] == 1
        assert _ids(embedding_store) == ["b", "c"]

    def test_force_reembeds_everything_without_duplicates(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "docs"
        _write_md(source_dir / "a.md", "alpha " * 40)
        _write_md(source_dir / "b.md", "beta " * 40)
        files = sorted(source_dir.glob("*.md"))
        _run_external(embedding_store, source_dir, files)

        forced = _run_external(embedding_store, source_dir, files, force=True)
        assert forced["embedded"] == 2
        assert forced["pruned"] == 0
        assert _ids(embedding_store) == ["a", "b"]

    def test_too_short_files_are_skipped(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "docs"
        _write_md(source_dir / "short.md", "tiny")
        _write_md(source_dir / "long.md", "long " * 40)
        files = sorted(source_dir.glob("*.md"))

        counts = _run_external(
            embedding_store,
            source_dir,
            files,
            min_chars=50,
        )
        assert counts["embedded"] == 1
        assert counts["skipped_empty"] == 1
        assert _ids(embedding_store) == ["long"]


# ---------------------------------------------------------------------------
# embed_digests sync loop
# ---------------------------------------------------------------------------


def _run_digests(
    store: Any,
    digests_dir: Path,
    digest_files: List[Path],
    **kwargs: Any,
) -> Dict[str, int]:
    return sync_digests(
        store=store,
        account="junwin",
        digests_dir=digests_dir,
        digest_files=digest_files,
        embed_fn=lambda text: _vector(len(text) % _DIM),
        log=_SILENT,
        **kwargs,
    )


class TestDigestsSync:
    def test_shared_session_digests_prune_by_record_id_only(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        digests_dir = tmp_path / "digests"
        _write_md(digests_dir / "sess-1_20260901.md", "alpha digest " * 20)
        _write_md(digests_dir / "sess-1_20260902.md", "beta digest " * 20)
        _write_md(digests_dir / "sess-2_20260901.md", "gamma digest " * 20)
        all_files = sorted(digests_dir.glob("*.md"))

        first = _run_digests(embedding_store, digests_dir, all_files)
        assert first["embedded"] == 3

        by_id = {
            record.id: record
            for record in embedding_store.list_embeddings("digests", "junwin")
        }
        assert set(by_id) == {
            "sess-1_20260901",
            "sess-1_20260902",
            "sess-2_20260901",
        }
        assert by_id["sess-1_20260901"].source_id == "sess-1"
        assert by_id["sess-1_20260902"].source_id == "sess-1"
        assert by_id["sess-2_20260901"].source_id == "sess-2"
        assert by_id["sess-1_20260901"].source_metadata["content_hash"] == sha256_file(
            digests_dir / "sess-1_20260901.md"
        )

        (digests_dir / "sess-1_20260902.md").unlink()
        remaining = sorted(digests_dir.glob("*.md"))

        second = _run_digests(embedding_store, digests_dir, remaining)
        assert second["embedded"] == 0
        assert second["skipped"] == 2
        assert second["pruned"] == 1

        survivors = embedding_store.list_embeddings("digests", "junwin")
        assert [record.id for record in survivors] == [
            "sess-1_20260901",
            "sess-2_20260901",
        ]
        assert survivors[0].source_id == "sess-1"

        third = _run_digests(embedding_store, digests_dir, remaining)
        assert third["embedded"] == 0
        assert third["skipped"] == 2
        assert third["pruned"] == 0
        assert len(embedding_store.list_embeddings("digests", "junwin")) == 2

    def test_digests_dry_run_writes_nothing(
        self, embedding_store: Any, tmp_path: Path
    ) -> None:
        digests_dir = tmp_path / "digests"
        _write_md(digests_dir / "sess-1_20260901.md", "alpha digest " * 20)
        _run_digests(
            embedding_store,
            digests_dir,
            sorted(digests_dir.glob("*.md")),
        )

        (digests_dir / "sess-1_20260901.md").unlink()
        _write_md(digests_dir / "sess-2_20260901.md", "beta digest " * 20)
        files = sorted(digests_dir.glob("*.md"))

        dry = _run_digests(embedding_store, digests_dir, files, dry_run=True)
        assert dry["embedded"] == 1
        assert dry["pruned"] == 1
        assert [r.id for r in embedding_store.list_embeddings("digests", "junwin")] == [
            "sess-1_20260901"
        ]
