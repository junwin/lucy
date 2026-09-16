"""Embedding store backed by the generic-store doc/log protocol.

Embedding records are stored as documents at logical keys

    embeddings/<account_name>/<namespace>/<id>.json

using only generic-store document operations plus ``list_keys`` for namespace
scans. Lucy owns the file/sqlite generic stores; native vector-index storage is
owned by galet-memory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.chat2.store_primitives import Chat2Primitives, StoreKey
from src.embeddings.comparison import cosine_similarity
from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt_utc(dt_str: str) -> datetime:
    if not dt_str:
        return _now_utc()
    value = str(dt_str).strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


class PrimitivesEmbeddingStore(EmbeddingStore):
    """EmbeddingStore implementation over generic-store primitives."""

    def __init__(self, store: Chat2Primitives) -> None:
        self._store = store

    @staticmethod
    def _record_key(account_name: str, namespace: str, record_id: str) -> StoreKey:
        return StoreKey(f"embeddings/{account_name}/{namespace}/{record_id}.json")

    @staticmethod
    def _account_prefix(account_name: str) -> StoreKey:
        return StoreKey(f"embeddings/{account_name}/")

    @staticmethod
    def _namespace_prefix(account_name: str, namespace: str) -> StoreKey:
        return StoreKey(f"embeddings/{account_name}/{namespace}/")

    @staticmethod
    def _to_doc(record: EmbeddingRecord) -> str:
        created = record.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        else:
            created = created.astimezone(timezone.utc)
        data = {
            "id": record.id,
            "namespace": record.namespace,
            "account_name": record.account_name,
            "vector": record.vector,
            "source_type": record.source_type,
            "source_id": record.source_id,
            "source_metadata": record.source_metadata,
            "created_at": created.isoformat(),
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def _from_doc(key: StoreKey, raw: str) -> Optional[EmbeddingRecord]:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError) as exc:
            logger.warning("primitives embedding store: skipping bad JSON at %s: %s", key, exc)
            return None
        vector = data.get("vector")
        if not isinstance(vector, list):
            logger.warning(
                "primitives embedding store: skipping record at %s (no vector)", key
            )
            return None
        return EmbeddingRecord(
            id=data.get("id", ""),
            namespace=data.get("namespace", ""),
            account_name=data.get("account_name", ""),
            vector=vector,
            source_type=data.get("source_type", ""),
            source_id=data.get("source_id", ""),
            source_metadata=data.get("source_metadata", {}) or {},
            created_at=_parse_dt_utc(data.get("created_at", "")),
        )

    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        key = self._record_key(record.account_name, record.namespace, record.id)
        self._store.write_text(key, self._to_doc(record))

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        prefix = f"embeddings/{account_name}/"
        namespaces: set[str] = set()
        for key in self._store.list_keys(self._account_prefix(account_name)):
            rest = key.value[len(prefix):]
            namespace = rest.split("/", 1)[0]
            if namespace:
                namespaces.add(namespace)
        return sorted(namespaces)

    def list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord]:
        records: List[EmbeddingRecord] = []
        prefix = self._namespace_prefix(account_name, namespace)
        for key in self._store.list_keys(prefix):
            raw = self._store.read_text(key)
            if raw is None:
                continue
            record = self._from_doc(key, raw)
            if record is not None:
                records.append(record)
        records.sort(key=lambda record: record.id)
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
        deleted = 0
        for key in self._store.list_keys(self._namespace_prefix(account_name, namespace)):
            raw = self._store.read_text(key)
            if raw is None:
                continue
            record = self._from_doc(key, raw)
            if record is None:
                continue
            if record_id is not None and record.id != record_id:
                continue
            if source_id is not None and record.source_id != source_id:
                continue
            if source_type is not None and record.source_type != source_type:
                continue
            self._store.delete(key)
            deleted += 1
        return deleted

    def query_embeddings(
        self,
        namespaces: List[str],
        account_name: str,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[EmbeddingRecord, float]]:
        results: List[Tuple[EmbeddingRecord, float]] = []
        for namespace in namespaces:
            for key in self._store.list_keys(
                self._namespace_prefix(account_name, namespace)
            ):
                raw = self._store.read_text(key)
                if raw is None:
                    continue
                record = self._from_doc(key, raw)
                if record is None:
                    continue
                if filter and "source_type" in filter:
                    if record.source_type != filter["source_type"]:
                        continue
                try:
                    similarity = cosine_similarity(query_vector, record.vector)
                except ValueError:
                    logger.warning(
                        "primitives embedding store: skipping %s (dim mismatch)", key
                    )
                    continue
                results.append((record, similarity))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:top_k]


def build_primitives_embedding_store(config: Any) -> EmbeddingStore:
    """Build one of Lucy's generic embedding stores.

    Supported backends are ``file`` and ``sqlite``. Native sqlite-vec/vec0
    persistence is owned by galet-memory and is intentionally not constructed
    here.
    """
    backend = str(config.get("embedding_store_backend", "file")).strip().lower()

    if backend == "sqlite":
        from src.chat2.sqlite import SqliteChat2Primitives

        db_path = config.get("embedding_store_db_path")
        if not db_path:
            storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
            storage_ns = config.get("storage_namespace") or "data"
            db_path = str(Path(storage_root) / storage_ns / "embeddings-v2.sqlite")
        return PrimitivesEmbeddingStore(SqliteChat2Primitives(db_path))

    if backend != "file":
        raise ValueError(
            f"Unknown embedding_store_backend {backend!r}: expected 'file' or 'sqlite'"
        )

    from src.chat2.fs_primitives import FileChat2Primitives

    storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
    storage_ns = config.get("storage_namespace") or "data"
    return PrimitivesEmbeddingStore(
        FileChat2Primitives(Path(storage_root) / storage_ns)
    )


__all__ = ["PrimitivesEmbeddingStore", "build_primitives_embedding_store"]
