from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.storage.models import EmbeddingRecord
from src.storage.vec0_embedding_store import (
    DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    Vec0EmbeddingStore,
)

_DIM = 1536


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
def db_path(tmp_path: Path) -> str:
    _require_vec0()
    return str(tmp_path / "canonical-vec0.sqlite")


def _record(
    record_id: str,
    *,
    source_type: str = "document",
    vector: list[float] | None = None,
) -> EmbeddingRecord:
    return EmbeddingRecord(
        id=record_id,
        account_name="junwin",
        namespace="documents",
        vector=vector if vector is not None else [1.0] + [0.0] * (_DIM - 1),
        source_type=source_type,
        source_id="notes/a.md",
        document_id="a" * 64,
        model="text-embedding-3-small",
        provider="openai",
        dimensions=_DIM,
        source_metadata={"path": "notes/a.md"},
    )


@pytest.mark.integration
def test_canonical_metadata_schema_and_round_trip(db_path: str) -> None:
    with Vec0EmbeddingStore(db_path) as store:
        store.upsert_embedding(_record("record-1"))
        records = store.list_embeddings("documents", "junwin")

    assert len(records) == 1
    record = records[0]
    assert record.id == "record-1"
    assert record.document_id == "a" * 64
    assert record.model == "text-embedding-3-small"
    assert record.provider == "openai"
    assert record.dimensions == _DIM
    assert record.source_metadata == {"path": "notes/a.md"}

    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(embedding_metadata)")}
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(embedding_metadata)")}
    finally:
        conn.close()

    assert {
        "id",
        "account_name",
        "namespace",
        "source_type",
        "source_id",
        "document_id",
        "model",
        "provider",
        "dimensions",
        "source_metadata",
        "created_at",
    } <= columns
    assert "idx_emb_meta_document_id" in indexes


@pytest.mark.integration
def test_source_type_filter_is_applied_before_final_top_k(db_path: str) -> None:
    query = [1.0] + [0.0] * (_DIM - 1)
    close_document = [0.99, 0.1] + [0.0] * (_DIM - 2)

    with Vec0EmbeddingStore(db_path) as store:
        store.upsert_embedding(_record("digest-best", source_type="digest", vector=query))
        store.upsert_embedding(
            _record("document-second", source_type="document", vector=close_document)
        )

        hits = store.query_embeddings(
            ["documents"],
            "junwin",
            query,
            top_k=1,
            filter={"source_type": "document"},
        )

    assert [record.id for record, _ in hits] == ["document-second"]


@pytest.mark.integration
def test_incompatible_dimensions_fail_explicitly(db_path: str) -> None:
    with Vec0EmbeddingStore(db_path) as store:
        with pytest.raises(ValueError, match="stored embedding dimension must be 1536"):
            store.upsert_embedding(_record("bad-store", vector=[1.0, 2.0]))

        store.upsert_embedding(_record("good"))
        with pytest.raises(ValueError, match="query embedding dimension must be 1536"):
            store.query_embeddings(["documents"], "junwin", [1.0, 2.0], top_k=1)


@pytest.mark.integration
def test_provenance_dimension_must_match_vector(db_path: str) -> None:
    record = _record("bad-provenance")
    record.dimensions = 3072

    with Vec0EmbeddingStore(db_path) as store:
        with pytest.raises(ValueError, match="provenance dimensions do not match"):
            store.upsert_embedding(record)
