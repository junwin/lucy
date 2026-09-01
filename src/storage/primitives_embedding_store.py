"""Embedding store backed by the generic-store doc/log protocol.

Second consumer of the generic store (after chat2's ``jsonl_store``), which
locks the protocol down: any backend that passes the conformance suite is a
drop-in. Embedding records are stored as **documents** at logical keys

    embeddings/<account_name>/<namespace>/<id>.json

using only the document ops (``read_text`` / ``write_text`` / ``exists`` /
``delete``) plus ``list_keys`` for namespace scans. Backends that implement
``Chat2Primitives`` work: ``InMemoryStore``, ``FileChat2Primitives``,
``SqliteChat2Primitives``, ``JfsChat2Primitives``.

Behavioral parity with ``JsonFileStorage``'s ``EmbeddingsMixin``:

- Same record JSON shape (``id``, ``namespace``, ``account_name``,
  ``vector``, ``source_type``, ``source_id``, ``source_metadata``,
  ``created_at``), so the file backend writes the exact same physical
  files as today's JSON store — the two are interchangeable on disk.
- ``query_embeddings`` supports the same ``{"source_type": ...}`` filter,
  merges results across namespaces, sorts by score descending, top_k.
- ``delete_embeddings`` filters by ``source_id`` and/or ``source_type``,
  returns the deleted count, idempotent.
- ``list_embedding_namespaces`` returns sorted namespace names.

With the sqlite backend, namespace scans become indexed prefix queries
(``list_keys`` -> ``LIKE ... ESCAPE``) instead of per-file glob IO — the
real win the generic-store design calls out.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.chat2.store_primitives import Chat2Primitives, StoreKey
from src.embeddings.comparison import cosine_similarity
from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timestamp helpers (parity with src/storage/json_file_storage_parts/embeddings.py)
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    """Return an offset-aware datetime in UTC."""
    return datetime.now(timezone.utc)


def _parse_dt_utc(dt_str: str) -> datetime:
    """Parse ISO timestamps from storage into an aware UTC datetime.

    Accepts:
      - "2023-06-14T21:58:27.803580Z"
      - "2023-06-14T21:58:27.803580+00:00"
      - naive "2023-06-14T21:58:27.803580" (assumed UTC)
    """
    if not dt_str:
        return _now_utc()

    s = str(dt_str).strip()
    # Support trailing "Z" (Zulu time)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)

    # If naive, assume UTC; if aware, normalize to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class PrimitivesEmbeddingStore(EmbeddingStore):
    """``EmbeddingStore`` implementation over generic-store primitives.

    Args:
        store: Any backend implementing the generic-store document ops plus
            ``list_keys`` (e.g. ``InMemoryStore``, ``FileChat2Primitives``,
            ``SqliteChat2Primitives``).
    """

    def __init__(self, store: Chat2Primitives) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Key layout
    # ------------------------------------------------------------------

    @staticmethod
    def _record_key(account_name: str, namespace: str, record_id: str) -> StoreKey:
        return StoreKey(f"embeddings/{account_name}/{namespace}/{record_id}.json")

    @staticmethod
    def _account_prefix(account_name: str) -> StoreKey:
        return StoreKey(f"embeddings/{account_name}/")

    @staticmethod
    def _namespace_prefix(account_name: str, namespace: str) -> StoreKey:
        return StoreKey(f"embeddings/{account_name}/{namespace}/")

    # ------------------------------------------------------------------
    # Serialization (parity with EmbeddingsMixin)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # EmbeddingStore interface
    # ------------------------------------------------------------------

    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        """Insert or update an embedding vector record.

        Same id + account + namespace => latest record wins (write_text is
        an atomic replace in every conformance-passing backend).
        """
        key = self._record_key(record.account_name, record.namespace, record.id)
        self._store.write_text(key, self._to_doc(record))

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        """List available embedding namespaces for an account, sorted.

        Returns [] if the account has no embeddings.
        """
        prefix = f"embeddings/{account_name}/"
        namespaces: set[str] = set()
        for key in self._store.list_keys(self._account_prefix(account_name)):
            rest = key.value[len(prefix):]
            namespace = rest.split("/", 1)[0]
            if namespace:
                namespaces.add(namespace)
        return sorted(namespaces)

    def delete_embeddings(
        self,
        namespace: str,
        account_name: str,
        *,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
    ) -> int:
        """Delete embedding records matching the given filters.

        Returns the count of deleted records. Idempotent: returns 0 if no
        matching records exist.
        """
        deleted = 0
        for key in self._store.list_keys(self._namespace_prefix(account_name, namespace)):
            raw = self._store.read_text(key)
            if raw is None:
                continue
            record = self._from_doc(key, raw)
            if record is None:
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
        """Vector search across one or more namespaces.

        Queries each namespace, merges all results, sorts by score
        descending, and returns the top_k across all namespaces combined.
        """
        results: List[Tuple[EmbeddingRecord, float]] = []

        for namespace in namespaces:
            prefix = self._namespace_prefix(account_name, namespace)
            for key in self._store.list_keys(prefix):
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
                    # Dimension mismatch on a stored record: skip it rather
                    # than failing the whole query.
                    logger.warning(
                        "primitives embedding store: skipping %s (dim mismatch)", key
                    )
                    continue

                results.append((record, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# ---------------------------------------------------------------------------
# Factory — config-driven backend selection
# ---------------------------------------------------------------------------

def build_primitives_embedding_store(config: Any) -> PrimitivesEmbeddingStore:
    """Build a PrimitivesEmbeddingStore from a ConfigManager-like object.

    Backend selection via ``embedding_store_backend`` (default ``file``):

    - ``file``   -> ``FileChat2Primitives`` over the same storage root as
      JsonFileStorage (``<storage_root_path>/<storage_namespace>``), so the
      on-disk layout is identical to today's JSON embedding store.
    - ``sqlite`` -> ``SqliteChat2Primitives`` at
      ``embedding_store_db_path`` (default
      ``<storage_root_path>/<storage_namespace>/embeddings.sqlite``).

    The default (``file``) keeps behavior byte-compatible with the existing
    store; ``sqlite`` is the protocol win (indexed prefix scans, no per-file
    IO).
    """
    backend = str(config.get("embedding_store_backend", "file")).strip().lower()

    if backend == "sqlite":
        from src.chat2.sqlite import SqliteChat2Primitives

        db_path = config.get("embedding_store_db_path")
        if not db_path:
            storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
            storage_ns = config.get("storage_namespace") or "data"
            db_path = str(Path(storage_root) / storage_ns / "embeddings.sqlite")
        return PrimitivesEmbeddingStore(SqliteChat2Primitives(db_path))

    # Default: file backend over the same root as JsonFileStorage.
    from src.chat2.fs_primitives import FileChat2Primitives

    storage_root = config.get("storage_root_path") or "/home/junwin/lucydata"
    storage_ns = config.get("storage_namespace") or "data"
    return PrimitivesEmbeddingStore(
        FileChat2Primitives(Path(storage_root) / storage_ns)
    )


__all__ = ["PrimitivesEmbeddingStore", "build_primitives_embedding_store"]
