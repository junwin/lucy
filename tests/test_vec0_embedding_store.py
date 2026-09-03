from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from scripts.migrate_embeddings_to_vec0 import migrate_embeddings_to_vec0
from src.chat2.sqlite import SqliteChat2Primitives
from src.chat2.store_primitives import StoreKey
from src.storage.models import EmbeddingRecord
from src.storage.primitives_embedding_store import PrimitivesEmbeddingStore
from src.storage.vec0_embedding_store import (
    DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    Vec0EmbeddingStore,
)

_DIM = 1536
_ACCOUNT = "junwin"
_NAMESPACES = ["vol_a", "vol_b", "vol_c"]
_SOURCE_TYPES = ["digest", "document", "book"]


def _vector(seed: int, dim: int = _DIM) -> List[float]:
    rng = random.Random(seed)
    vector = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    if not any(vector):
        vector[0] = 0.5
    return vector


def _make_record(
    record_id: str,
    namespace: str,
    *,
    account: str = _ACCOUNT,
    seed: int = 0,
    vector: Optional[List[float]] = None,
    source_type: str = "document",
    source_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> EmbeddingRecord:
    return EmbeddingRecord(
        id=record_id,
        namespace=namespace,
        account_name=account,
        vector=_vector(seed) if vector is None else vector,
        source_type=source_type,
        source_id=source_id,
        source_metadata=metadata if metadata is not None else {},
    )


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


@pytest.fixture
def vec0_db_path(tmp_path: Path) -> str:
    _require_vec0()
    return str(tmp_path / "vec0.sqlite")


def _open_with_vec0(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension(DEFAULT_SQLITE_VEC_EXTENSION_PATH)
    return conn


def _scalar(db_path: str, sql: str, params: Tuple[Any, ...] = ()) -> Any:
    conn = _open_with_vec0(db_path)
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def _query_all(db_path: str, sql: str, params: Tuple[Any, ...] = ()) -> List[Tuple[Any, ...]]:
    conn = _open_with_vec0(db_path)
    try:
        return [tuple(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _vec0_distance(db_path: str, query_vector: List[float]) -> float:
    conn = _open_with_vec0(db_path)
    try:
        row = conn.execute(
            "SELECT distance FROM vec_embeddings"
            " WHERE embedding MATCH ? AND k = 1 AND account_name = ? AND namespace = ?",
            (json.dumps(query_vector), _ACCOUNT, "documents"),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return row[0]


@pytest.mark.unit
def test_query_score_is_one_minus_vec0_distance(vec0_db_path: str) -> None:
    vec = _vector(seed=1)
    with Vec0EmbeddingStore(vec0_db_path) as store:
        store.upsert_embedding(_make_record("r1", "documents", seed=1, vector=vec))
        store.upsert_embedding(_make_record("r2", "other", seed=2))
        queries = [vec, [-1.0 * x for x in vec], _vector(seed=3)]
        for query in queries:
            results = store.query_embeddings(["documents"], _ACCOUNT, query, top_k=1)
            assert len(results) == 1
            assert results[0][0].id == "r1"
            distance = _vec0_distance(vec0_db_path, query)
            assert results[0][1] == pytest.approx(1.0 - distance, abs=1e-12)
    assert _vec0_distance(vec0_db_path, vec) == pytest.approx(0.0, abs=1e-6)
    assert _vec0_distance(vec0_db_path, [-1.0 * x for x in vec]) == pytest.approx(
        2.0, abs=1e-6
    )


@pytest.mark.unit
def test_filter_source_type_and_unknown_keys(vec0_db_path: str) -> None:
    with Vec0EmbeddingStore(vec0_db_path) as store:
        store.upsert_embedding(
            _make_record("dig-1", "documents", seed=1, source_type="digest")
        )
        store.upsert_embedding(
            _make_record("doc-1", "documents", seed=2, source_type="document")
        )
        query = _vector(seed=3)

        def ids(filter: Optional[Dict[str, Any]]) -> List[str]:
            results = store.query_embeddings(
                ["documents"], _ACCOUNT, query, top_k=10, filter=filter
            )
            return sorted(record.id for record, _ in results)

        assert ids({"source_type": "digest"}) == ["dig-1"]
        assert ids({"source_type": "document"}) == ["doc-1"]
        assert ids({"source_type": "digest", "unknown": True}) == ["dig-1"]
        assert ids({"unknown_key": "x", "another": 1}) == ["dig-1", "doc-1"]
        assert ids(None) == ["dig-1", "doc-1"]


@pytest.mark.unit
def test_upsert_rejects_non_1536_dimension(vec0_db_path: str) -> None:
    with Vec0EmbeddingStore(vec0_db_path) as store:
        with pytest.raises(AssertionError, match="embedding dimension must be 1536"):
            store.upsert_embedding(_make_record("short", "documents", vector=[1.0, 2.0]))
        with pytest.raises(AssertionError, match="embedding dimension must be 1536"):
            store.upsert_embedding(
                _make_record("long", "documents", vector=[0.0] * 1537)
            )
        store.upsert_embedding(_make_record("good", "documents", seed=7))
        results = store.query_embeddings(
            ["documents"], _ACCOUNT, _vector(seed=7), top_k=1
        )
        assert [record.id for record, _ in results] == ["good"]


@pytest.mark.integration
def test_round_trip_upsert_query_delete(vec0_db_path: str) -> None:
    with Vec0EmbeddingStore(vec0_db_path) as store:
        store.upsert_embedding(
            _make_record(
                "doc-1",
                "documents",
                seed=1,
                source_type="document",
                source_id="/notes/a.md",
                metadata={"path": "/notes/a.md"},
            )
        )
        store.upsert_embedding(
            _make_record(
                "doc-2",
                "documents",
                seed=2,
                source_type="document",
                source_id="/notes/b.md",
            )
        )
        store.upsert_embedding(
            _make_record(
                "dig-1",
                "digests",
                seed=3,
                source_type="digest",
                source_id="sess-7",
                metadata={"session_id": "sess-7"},
            )
        )

        results = store.query_embeddings(
            ["documents", "digests"], _ACCOUNT, _vector(seed=1), top_k=10
        )
        by_id = {record.id: record for record, _ in results}
        assert set(by_id) == {"doc-1", "doc-2", "dig-1"}
        assert results[0][0].id == "doc-1"
        assert results[0][1] == pytest.approx(1.0, abs=1e-6)
        assert by_id["doc-1"].source_metadata == {"path": "/notes/a.md"}
        assert by_id["dig-1"].source_metadata == {"session_id": "sess-7"}

        assert (
            store.delete_embeddings(
                "documents", _ACCOUNT, source_id="/notes/a.md"
            )
            == 1
        )
        remaining = store.query_embeddings(
            ["documents"], _ACCOUNT, _vector(seed=1), top_k=10
        )
        assert [record.id for record, _ in remaining] == ["doc-2"]
        assert (
            store.delete_embeddings(
                "documents", _ACCOUNT, source_id="/notes/a.md"
            )
            == 0
        )

        digests = store.query_embeddings(
            ["digests"], _ACCOUNT, _vector(seed=3), top_k=10
        )
        assert [record.id for record, _ in digests] == ["dig-1"]
        assert store.delete_embeddings("digests", _ACCOUNT, source_type="digest") == 1
        assert (
            store.query_embeddings(["digests"], _ACCOUNT, _vector(seed=3), top_k=10)
            == []
        )
        assert store.delete_embeddings("digests", _ACCOUNT, source_type="digest") == 0

        store.upsert_embedding(
            _make_record(
                "doc-2",
                "documents",
                seed=9,
                source_type="document",
                source_id="/notes/b.md",
                metadata={"path": "/notes/b.md", "rev": 2},
            )
        )
        latest = store.query_embeddings(
            ["documents"], _ACCOUNT, _vector(seed=9), top_k=10
        )
        assert len(latest) == 1
        assert latest[0][0].id == "doc-2"
        assert latest[0][1] == pytest.approx(1.0, abs=1e-6)
        assert latest[0][0].source_metadata == {"path": "/notes/b.md", "rev": 2}
        assert (
            _scalar(
                vec0_db_path,
                "SELECT COUNT(*) FROM vec_embeddings WHERE id = ?",
                ("doc-2",),
            )
            == 1
        )
        assert (
            _scalar(
                vec0_db_path,
                "SELECT COUNT(*) FROM embedding_metadata WHERE id = ?",
                ("doc-2",),
            )
            == 1
        )

        assert store.delete_embeddings("documents", _ACCOUNT) == 1
        assert (
            store.query_embeddings(["documents"], _ACCOUNT, _vector(seed=1), top_k=10)
            == []
        )
        assert store.delete_embeddings("documents", _ACCOUNT) == 0


@pytest.mark.integration
def test_migration_idempotent_scratch_db_counts_stable(vec0_db_path: str) -> None:
    kv_backend = SqliteChat2Primitives(vec0_db_path)
    brute = PrimitivesEmbeddingStore(kv_backend)
    try:
        for i in range(3):
            brute.upsert_embedding(
                _make_record(
                    f"doc-{i}", "documents", seed=10 + i, source_id=f"/notes/{i}.md"
                )
            )
        for i in range(2):
            brute.upsert_embedding(
                _make_record(
                    f"dig-{i}",
                    "digests",
                    seed=20 + i,
                    source_type="digest",
                    source_id=f"sess-{i}",
                )
            )

        def snapshot() -> List[Tuple[str, Optional[str]]]:
            keys = sorted(
                key.value for key in kv_backend.list_keys(StoreKey("embeddings/"))
            )
            return [(key, kv_backend.read_text(StoreKey(key))) for key in keys]

        before = snapshot()

        dry = migrate_embeddings_to_vec0(
            vec0_db_path, _ACCOUNT, DEFAULT_SQLITE_VEC_EXTENSION_PATH, dry_run=True
        )
        assert dry["parsed_counts"] == {"documents": 3, "digests": 2}
        assert dry["skipped"] == []
        assert dry["vec_counts"] is None
        table_names = {
            row[0]
            for row in _query_all(
                vec0_db_path,
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')",
            )
        }
        assert "vec_embeddings" not in table_names

        first = migrate_embeddings_to_vec0(
            vec0_db_path, _ACCOUNT, DEFAULT_SQLITE_VEC_EXTENSION_PATH
        )
        assert first["parsed_counts"] == {"documents": 3, "digests": 2}
        assert first["skipped"] == []
        assert first["vec_counts"] == {"documents": 3, "digests": 2}
        assert first["metadata_counts"] == {"documents": 3, "digests": 2}
        assert snapshot() == before

        second = migrate_embeddings_to_vec0(
            vec0_db_path, _ACCOUNT, DEFAULT_SQLITE_VEC_EXTENSION_PATH
        )
        assert second["vec_counts"] == first["vec_counts"]
        assert second["metadata_counts"] == first["metadata_counts"]
        assert snapshot() == before

        assert _scalar(vec0_db_path, "SELECT COUNT(*) FROM vec_embeddings") == 5
        assert _scalar(vec0_db_path, "SELECT COUNT(*) FROM embedding_metadata") == 5
        assert dict(
            _query_all(
                vec0_db_path,
                "SELECT namespace, COUNT(*) FROM embedding_metadata"
                " GROUP BY namespace ORDER BY namespace",
            )
        ) == {"digests": 2, "documents": 3}
    finally:
        kv_backend.close()


@pytest.mark.integration
def test_parity_with_brute_force_primitives_path(vec0_db_path: str) -> None:
    kv_backend = SqliteChat2Primitives(vec0_db_path)
    brute = PrimitivesEmbeddingStore(kv_backend)
    try:
        counts = {"vol_a": 12, "vol_b": 9, "vol_c": 6}
        records: List[EmbeddingRecord] = []
        seed = 100
        for namespace in _NAMESPACES:
            for i in range(counts[namespace]):
                records.append(
                    _make_record(
                        f"{namespace}-{i}",
                        namespace,
                        seed=seed,
                        source_type=_SOURCE_TYPES[seed % len(_SOURCE_TYPES)],
                        source_id=f"src-{seed}",
                    )
                )
                seed += 1
        for record in records:
            brute.upsert_embedding(record)

        with Vec0EmbeddingStore(vec0_db_path) as vec_store:
            for record in records:
                vec_store.upsert_embedding(record)

            queries = [
                records[0].vector,
                [2.0 * x for x in records[5].vector],
                [-1.0 * x for x in records[12].vector],
                _vector(seed=4242),
            ]
            for query in queries:
                for top_k in (1, 3, 10, 15):
                    expected = brute.query_embeddings(
                        _NAMESPACES, _ACCOUNT, query, top_k=top_k
                    )
                    actual = vec_store.query_embeddings(
                        _NAMESPACES, _ACCOUNT, query, top_k=top_k
                    )
                    assert [record.id for record, _ in expected] == [
                        record.id for record, _ in actual
                    ]
                    assert len(actual) == top_k
                    for (_, brute_score), (_, vec_score) in zip(expected, actual):
                        assert abs(brute_score - vec_score) <= 1e-6
                full_expected = brute.query_embeddings(
                    _NAMESPACES, _ACCOUNT, query, top_k=50
                )
                full_actual = vec_store.query_embeddings(
                    _NAMESPACES, _ACCOUNT, query, top_k=50
                )
                assert {record.id for record, _ in full_expected} == {
                    record.id for record, _ in full_actual
                }
                assert len(full_actual) == len(records)
                assert [score for _, score in full_expected] == pytest.approx(
                    [score for _, score in full_actual], abs=1e-6
                )

            for top_k in (1, 5, 9):
                expected = brute.query_embeddings(
                    _NAMESPACES,
                    _ACCOUNT,
                    queries[3],
                    top_k=top_k,
                    filter={"source_type": "digest"},
                )
                actual = vec_store.query_embeddings(
                    _NAMESPACES,
                    _ACCOUNT,
                    queries[3],
                    top_k=top_k,
                    filter={"source_type": "digest"},
                )
                assert [record.id for record, _ in expected] == [
                    record.id for record, _ in actual
                ]
                for (_, brute_score), (_, vec_score) in zip(expected, actual):
                    assert abs(brute_score - vec_score) <= 1e-6
    finally:
        kv_backend.close()
