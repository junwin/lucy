"""Compatibility adapter for Lucy callers that still use Vec0EmbeddingStore.

Native sqlite-vec ownership lives in ``galet-memory``.  This module only adapts
its ``SqliteVecEmbeddingIndex`` to Lucy's historical ``EmbeddingStore`` shape
while remaining mixed Lucy tests and callers are migrated.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from galet_memory.ports import StoredEmbedding
from galet_memory.ports.sqlite_vec import (
    DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    EmbeddingCompatibilityError,
    SqliteVecEmbeddingIndex,
)

from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord


class Vec0EmbeddingStore(EmbeddingStore):
    """Lucy EmbeddingStore adapter over galet-memory's sqlite-vec index."""

    def __init__(
        self,
        db_path: str,
        sqlite_vec_extension_path: str | None = DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    ) -> None:
        extension_path: str | None = sqlite_vec_extension_path
        if extension_path == DEFAULT_SQLITE_VEC_EXTENSION_PATH and not Path(extension_path).exists():
            extension_path = None
        self._index = SqliteVecEmbeddingIndex(
            db_path,
            sqlite_vec_extension_path=extension_path,
        )

    @staticmethod
    def _to_stored(record: EmbeddingRecord) -> StoredEmbedding:
        return StoredEmbedding(
            id=record.id,
            account_name=record.account_name,
            namespace=record.namespace,
            vector=record.vector,
            source_type=record.source_type,
            source_id=record.source_id,
            metadata=record.source_metadata,
            created_at=record.created_at,
        )

    @staticmethod
    def _from_row(row: tuple[Any, ...], vector: List[float]) -> EmbeddingRecord:
        created_at = datetime.fromisoformat(str(row[6]))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return EmbeddingRecord(
            id=str(row[0]),
            account_name=str(row[1]),
            namespace=str(row[2]),
            vector=vector,
            source_type=str(row[3] or ""),
            source_id=str(row[4] or ""),
            source_metadata=json.loads(row[5] or "{}"),
            created_at=created_at,
        )

    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        self._index.upsert(self._to_stored(record))

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        return list(self._index.list_namespaces(account_name))

    def list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord]:
        conn = self._index._conn
        metadata_rows = conn.execute(
            "SELECT id, account_name, namespace, source_type, source_id, "
            "source_metadata, created_at FROM embedding_metadata "
            "WHERE account_name=? AND namespace=? ORDER BY id",
            (account_name, namespace),
        ).fetchall()
        records: List[EmbeddingRecord] = []
        for row in metadata_rows:
            vector_row = conn.execute(
                f"SELECT embedding FROM {self._index.vector_table} WHERE id=?",
                (row[0],),
            ).fetchone()
            if vector_row is None:
                continue
            blob = vector_row[0]
            if isinstance(blob, bytes):
                import struct

                vector = list(struct.unpack(f"<{len(blob) // 4}f", blob))
            else:
                vector = list(json.loads(blob)) if isinstance(blob, str) else list(blob)
            records.append(self._from_row(row, vector))
        return records

    def delete_embeddings(
        self,
        namespace: str,
        account_name: str,
        *,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> int:
        matches = self.list_embeddings(namespace, account_name)
        selected = [
            record
            for record in matches
            if (record_id is None or record.id == record_id)
            and (source_id is None or record.source_id == source_id)
            and (source_type is None or record.source_type == source_type)
        ]
        conn = self._index._conn
        for record in selected:
            conn.execute(
                f"DELETE FROM {self._index.vector_table} WHERE id=?", (record.id,)
            )
            conn.execute("DELETE FROM embedding_metadata WHERE id=?", (record.id,))
        return len(selected)

    def query_embeddings(
        self,
        namespaces: List[str],
        account_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[EmbeddingRecord, float]]:
        matches = self._index.query(
            account_name=account_name,
            namespaces=namespaces,
            vector=query_vector,
            limit=top_k,
            filters=filter,
        )
        records_by_id = {
            record.id: record
            for namespace in namespaces
            for record in self.list_embeddings(namespace, account_name)
        }
        return [
            (records_by_id[match.record.id], match.score)
            for match in matches
            if match.record.id in records_by_id
        ]

    def close(self) -> None:
        self._index.close()

    def __enter__(self) -> "Vec0EmbeddingStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


__all__ = [
    "DEFAULT_SQLITE_VEC_EXTENSION_PATH",
    "EmbeddingCompatibilityError",
    "Vec0EmbeddingStore",
]
