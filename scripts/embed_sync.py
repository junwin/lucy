from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, List, Optional

from src.storage.interfaces import EmbeddingStore
from src.storage.models import EmbeddingRecord


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stored_content_hash(record: Optional[EmbeddingRecord]) -> Optional[str]:
    if record is None:
        return None
    value = (record.source_metadata or {}).get("content_hash")
    if value is None:
        return None
    return str(value)


def is_unchanged(record: Optional[EmbeddingRecord], current_hash: str) -> bool:
    return stored_content_hash(record) == current_hash


def resolve_record_source_path(record: EmbeddingRecord, source_root: Path) -> Optional[Path]:
    root = source_root.resolve()
    metadata = record.source_metadata or {}
    raw_path = metadata.get("path")
    if raw_path:
        candidate = Path(str(raw_path))
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if resolved.is_relative_to(root):
                return resolved
    raw_relative = metadata.get("relative_path")
    if raw_relative:
        candidate = Path(str(raw_relative))
        if not candidate.is_absolute():
            resolved = (root / candidate).resolve()
            if resolved.is_relative_to(root):
                return resolved
    return None


def prune_missing(
    store: EmbeddingStore,
    *,
    account_name: str,
    namespace: str,
    source_root: Path,
    dry_run: bool = False,
    log: Callable[[str], None] = print,
) -> List[str]:
    records = store.list_embeddings(namespace, account_name)
    candidates: List[EmbeddingRecord] = []
    for record in records:
        path = resolve_record_source_path(record, source_root)
        if path is not None and not path.exists():
            candidates.append(record)
    candidates.sort(key=lambda record: record.id)
    removed: List[str] = []
    for record in candidates:
        if dry_run:
            log(f"  WOULD PRUNE (source missing): {record.id}")
        else:
            log(f"  PRUNED (source missing): {record.id}")
            store.delete_embeddings(namespace, account_name, record_id=record.id)
        removed.append(record.id)
    return removed


class StoreConfig:
    def __init__(self, config: Any, storage_root: str, storage_namespace: str) -> None:
        self._config = config
        self._storage_root = storage_root
        self._storage_namespace = storage_namespace

    def get(self, key: str, default: Any = None) -> Any:
        if key == "storage_root_path":
            return self._storage_root
        if key == "storage_namespace":
            return self._storage_namespace
        return self._config.get(key, default)
