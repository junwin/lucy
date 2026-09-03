from __future__ import annotations

import json
import sqlite3
import struct
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord

DEFAULT_SQLITE_VEC_EXTENSION_PATH = "/usr/local/lib/sqlite-vec/vec0.so"

_EMBEDDING_DIM = 1536

_VEC_TABLE_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0("
    " id TEXT,"
    " embedding float[1536] distance_metric=cosine,"
    " account_name TEXT,"
    " namespace TEXT,"
    " source_type TEXT)"
)

_METADATA_TABLE_DDL = (
    "CREATE TABLE IF NOT EXISTS embedding_metadata ("
    " id TEXT PRIMARY KEY,"
    " account_name TEXT NOT NULL,"
    " namespace TEXT NOT NULL,"
    " source_type TEXT NOT NULL DEFAULT '',"
    " source_id TEXT NOT NULL DEFAULT '',"
    " source_metadata TEXT NOT NULL DEFAULT '{}',"
    " created_at TEXT NOT NULL)"
)

_ACCOUNT_NS_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_emb_meta_account_ns"
    " ON embedding_metadata(account_name, namespace)"
)

_SOURCE_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_emb_meta_source"
    " ON embedding_metadata(source_type, source_id)"
)

_VEC_INSERT_SQL = (
    "INSERT INTO vec_embeddings(id, account_name, namespace, source_type, embedding)"
    " VALUES (?, ?, ?, ?, ?)"
)

_VEC_SELECT_ROWIDS_SQL = "SELECT rowid FROM vec_embeddings WHERE id = ?"

_VEC_DELETE_BY_ROWID_SQL = "DELETE FROM vec_embeddings WHERE rowid = ?"

_METADATA_UPSERT_SQL = (
    "INSERT INTO embedding_metadata("
    " id, account_name, namespace, source_type, source_id, source_metadata, created_at"
    ") VALUES (?, ?, ?, ?, ?, ?, ?)"
    " ON CONFLICT(id) DO UPDATE SET"
    " account_name = excluded.account_name,"
    " namespace = excluded.namespace,"
    " source_type = excluded.source_type,"
    " source_id = excluded.source_id,"
    " source_metadata = excluded.source_metadata,"
    " created_at = excluded.created_at"
)

_METADATA_SELECT_COLUMNS = (
    "id, account_name, namespace, source_type, source_id, source_metadata, created_at"
)

_KNN_SELECT_SQL = (
    "SELECT id, embedding, distance FROM vec_embeddings"
    " WHERE embedding MATCH ? AND k = ? AND account_name = ? AND namespace = ?"
)

_NAMESPACE_SELECT_SQL = (
    "SELECT DISTINCT namespace FROM embedding_metadata"
    " WHERE account_name = ? ORDER BY namespace"
)

_LIST_METADATA_SQL = (
    "SELECT id, account_name, namespace, source_type, source_id, source_metadata, created_at"
    " FROM embedding_metadata WHERE account_name = ? AND namespace = ? ORDER BY id"
)


def _to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _from_utc_iso(value: str) -> datetime:
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _decode_vector(blob: bytes) -> List[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


class Vec0EmbeddingStore(EmbeddingStore):
    def __init__(
        self,
        db_path: str,
        sqlite_vec_extension_path: str = DEFAULT_SQLITE_VEC_EXTENSION_PATH,
    ) -> None:
        self._conn = sqlite3.connect(
            str(db_path), check_same_thread=False, isolation_level=None
        )
        self._lock = threading.RLock()
        self._conn.enable_load_extension(True)
        self._conn.load_extension(sqlite_vec_extension_path)
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(_VEC_TABLE_DDL)
            self._conn.execute(_METADATA_TABLE_DDL)
            self._conn.execute(_ACCOUNT_NS_INDEX_DDL)
            self._conn.execute(_SOURCE_INDEX_DDL)

    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        if len(record.vector) != _EMBEDDING_DIM:
            raise AssertionError(
                f"embedding dimension must be {_EMBEDDING_DIM}, got {len(record.vector)}"
            )
        created_at = _to_utc_iso(record.created_at)
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                rowids = self._conn.execute(
                    _VEC_SELECT_ROWIDS_SQL, (record.id,)
                ).fetchall()
                for (rowid,) in rowids:
                    self._conn.execute(_VEC_DELETE_BY_ROWID_SQL, (rowid,))
                self._conn.execute(
                    _VEC_INSERT_SQL,
                    (
                        record.id,
                        record.account_name,
                        record.namespace,
                        record.source_type,
                        json.dumps(record.vector),
                    ),
                )
                self._conn.execute(
                    _METADATA_UPSERT_SQL,
                    (
                        record.id,
                        record.account_name,
                        record.namespace,
                        record.source_type,
                        record.source_id,
                        json.dumps(record.source_metadata or {}),
                        created_at,
                    ),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def query_embeddings(
        self,
        namespaces: List[str],
        account_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[EmbeddingRecord, float]]:
        if top_k <= 0:
            return []
        has_source_type = filter is not None and "source_type" in filter
        source_type = filter["source_type"] if has_source_type else None
        match = json.dumps(query_vector)
        results: List[Tuple[EmbeddingRecord, float]] = []
        with self._lock:
            for namespace in namespaces:
                sql = _KNN_SELECT_SQL
                params: List[Any] = [match, top_k, account_name, namespace]
                if has_source_type:
                    sql = sql + " AND source_type = ?"
                    params.append(source_type)
                rows = self._conn.execute(sql, params).fetchall()
                if not rows:
                    continue
                metadata = self._fetch_metadata([row[0] for row in rows])
                for record_id, blob, distance in rows:
                    meta = metadata.get(record_id)
                    if meta is None:
                        continue
                    results.append(
                        (
                            EmbeddingRecord(
                                id=meta[0],
                                account_name=meta[1],
                                namespace=meta[2],
                                source_type=meta[3],
                                source_id=meta[4],
                                source_metadata=json.loads(meta[5] or "{}"),
                                created_at=_from_utc_iso(meta[6]),
                                vector=_decode_vector(blob),
                            ),
                            1.0 - distance,
                        )
                    )
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]

    def list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord]:
        """Return all embedding records in a namespace for an account, sorted by id."""
        with self._lock:
            rows = self._conn.execute(
                _LIST_METADATA_SQL, (account_name, namespace)
            ).fetchall()
            if not rows:
                return []
            vector_blobs = self._fetch_vector_blobs([row[0] for row in rows])
        records: List[EmbeddingRecord] = []
        for meta in rows:
            blob = vector_blobs.get(meta[0])
            if blob is None:
                continue
            records.append(
                EmbeddingRecord(
                    id=meta[0],
                    account_name=meta[1],
                    namespace=meta[2],
                    source_type=meta[3],
                    source_id=meta[4],
                    source_metadata=json.loads(meta[5] or "{}"),
                    created_at=_from_utc_iso(meta[6]),
                    vector=_decode_vector(blob),
                )
            )
        return records

    def _fetch_vector_blobs(self, record_ids: List[str]) -> Dict[str, bytes]:
        if not record_ids:
            return {}
        placeholders = ", ".join("?" for _ in record_ids)
        sql = (
            "SELECT id, embedding FROM vec_embeddings WHERE id IN ("
            + placeholders
            + ")"
        )
        rows = self._conn.execute(sql, record_ids).fetchall()
        return {row[0]: row[1] for row in rows}

    def delete_embeddings(
        self,
        namespace: str,
        account_name: str,
        *,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> int:
        clauses = ["account_name = ?", "namespace = ?"]
        params: List[Any] = [account_name, namespace]
        if record_id is not None:
            clauses.append("id = ?")
            params.append(record_id)
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        select_sql = "SELECT id FROM embedding_metadata WHERE " + " AND ".join(clauses)
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                record_ids = [
                    row[0]
                    for row in self._conn.execute(select_sql, params).fetchall()
                ]
                for record_id in record_ids:
                    rowids = self._conn.execute(
                        _VEC_SELECT_ROWIDS_SQL, (record_id,)
                    ).fetchall()
                    for (rowid,) in rowids:
                        self._conn.execute(_VEC_DELETE_BY_ROWID_SQL, (rowid,))
                for record_id in record_ids:
                    self._conn.execute(
                        "DELETE FROM embedding_metadata WHERE id = ?",
                        (record_id,),
                    )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return len(record_ids)

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                _NAMESPACE_SELECT_SQL, (account_name,)
            ).fetchall()
        return [row[0] for row in rows]

    def _fetch_metadata(
        self, record_ids: List[str]
    ) -> Dict[str, Tuple[str, str, str, str, str, str, str]]:
        if not record_ids:
            return {}
        placeholders = ", ".join("?" for _ in record_ids)
        rows = self._conn.execute(
            "SELECT "
            + _METADATA_SELECT_COLUMNS
            + " FROM embedding_metadata WHERE id IN ("
            + placeholders
            + ")",
            record_ids,
        ).fetchall()
        return {row[0]: row for row in rows}

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "Vec0EmbeddingStore":
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()


__all__ = [
    "Vec0EmbeddingStore",
    "DEFAULT_SQLITE_VEC_EXTENSION_PATH",
]
