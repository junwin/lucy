"""Embedding methods for JsonFileStorage (mixin part).

Provides the EmbeddingsMixin class: embedding methods that operate on a
JsonFileStorage instance (self.storage_paths, self._load_json,
self._ensure_dir, self._atomic_write).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.storage.models import EmbeddingRecord


def _now_utc() -> datetime:
    """Return an offset-aware datetime in UTC."""
    return datetime.now(timezone.utc)


def _parse_dt_utc(dt_str: str) -> datetime:
    """
    Parse ISO timestamps from storage into an aware UTC datetime.

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


class EmbeddingsMixin:
    """Embedding methods extracted from JsonFileStorage.

    Mixin: relies on self.storage_paths, self._load_json, self._ensure_dir,
    and self._atomic_write provided by the composing class.
    """

    # ----------------------------------------------------------------------
    # EMBEDDINGS
    # ----------------------------------------------------------------------

    def upsert_embedding(self, record: EmbeddingRecord) -> None:
        path = (
            self.storage_paths.base
            / "embeddings"
            / record.account_name
            / record.namespace
        )
        self._ensure_dir(path)

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

        self._atomic_write(path / f"{record.id}.json", data)

    def list_embedding_namespaces(self, account_name: str) -> List[str]:
        """List available embedding namespaces for an account.

        Returns subdirectory names under embeddings/<account_name>/,
        sorted alphabetically. Returns empty list if the account has
        no embeddings.
        """
        emb_dir = self.storage_paths.base / "embeddings" / account_name
        if not emb_dir.exists() or not emb_dir.is_dir():
            return []

        namespaces: List[str] = []
        for p in emb_dir.iterdir():
            if p.is_dir():
                namespaces.append(p.name)

        namespaces.sort()
        return namespaces

    def list_embeddings(self, namespace: str, account_name: str) -> List[EmbeddingRecord]:
        """Return all embedding records in a namespace for an account, sorted by id."""
        path = self.storage_paths.base / "embeddings" / account_name / namespace
        if not path.exists():
            return []

        records: List[EmbeddingRecord] = []
        for emb_file in sorted(path.glob("*.json")):
            data = self._load_json(emb_file)
            if not data or not isinstance(data.get("vector"), list):
                continue
            records.append(
                EmbeddingRecord(
                    id=data["id"],
                    namespace=data["namespace"],
                    account_name=data["account_name"],
                    vector=data["vector"],
                    source_type=data["source_type"],
                    source_id=data["source_id"],
                    source_metadata=data.get("source_metadata", {}) or {},
                    created_at=_parse_dt_utc(data.get("created_at", "")),
                )
            )
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
        """Delete embedding records matching the given filters.

        Returns count of deleted records. Idempotent: returns 0 if no
        matching records exist.
        """
        path = self.storage_paths.base / "embeddings" / account_name / namespace
        if not path.exists():
            return 0

        deleted = 0
        for emb_file in path.glob("*.json"):
            data = self._load_json(emb_file)
            if not data:
                continue
            if record_id is not None and data.get("id") != record_id:
                continue
            if source_id is not None and data.get("source_id") != source_id:
                continue
            if source_type is not None and data.get("source_type") != source_type:
                continue
            try:
                emb_file.unlink()
                deleted += 1
            except Exception as e:
                logging.error("Failed to delete embedding file %s: %s", emb_file, e)

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

        Queries each namespace, merges all results, sorts by score descending,
        and returns the top_k across all namespaces combined.
        """
        results: List[Tuple[EmbeddingRecord, float]] = []

        for namespace in namespaces:
            path = self.storage_paths.base / "embeddings" / account_name / namespace
            if not path.exists():
                continue

            for emb_file in path.glob("*.json"):
                data = self._load_json(emb_file)
                if not data:
                    continue

                if filter and "source_type" in filter:
                    if data.get("source_type") != filter["source_type"]:
                        continue

                vector = data["vector"]
                similarity = self._cosine_similarity(query_vector, vector)

                record = EmbeddingRecord(
                    id=data["id"],
                    namespace=data["namespace"],
                    account_name=data["account_name"],
                    vector=vector,
                    source_type=data["source_type"],
                    source_id=data["source_id"],
                    source_metadata=data.get("source_metadata", {}),
                    created_at=_parse_dt_utc(data.get("created_at", "")),
                )

                results.append((record, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    # ----------------------------------------------------------------------
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(b * b for b in vec2))

        if mag1 == 0 or mag2 == 0:
            return 0.0
        return dot / (mag1 * mag2)
