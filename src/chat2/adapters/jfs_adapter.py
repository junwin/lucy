"""
JFS (JsonFileStorage) adapter for Chat v2 storage primitives.

Wraps an existing JsonFileStorage instance to implement Chat2Primitives.
Maps logical StoreKey paths to filesystem paths under the storage's base
namespace, reusing JsonFileStorage's atomic write helpers.

This adapter does NOT modify JsonFileStorage - it composes with it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.chat2.store_primitives import Chat2Primitives, StoreKey
from src.storage.json_file_storage import JsonFileStorage


class JfsChat2Primitives:
    """Chat2Primitives adapter backed by a JsonFileStorage instance.

    Maps StoreKey paths (e.g. ``sessions/<id>/meta.json``) to real paths
    under the storage's base directory, using a ``chat2/`` subdirectory
    to avoid collisions with existing v1 data.

    Reuses JsonFileStorage's ``_atomic_write_text`` helper for safe writes.

    Args:
        storage: An existing JsonFileStorage instance.
    """

    def __init__(self, storage: JsonFileStorage) -> None:
        self._storage = storage
        # Root for chat2 data: <storage_base>/chat2/
        self._root = storage.storage_paths.base / "chat2"

    def _resolve(self, key: StoreKey) -> Path:
        """Resolve a StoreKey to an absolute filesystem path.

        Security: ensures the resolved path stays within root.
        """
        path = (self._root / key.value).resolve()
        if not str(path).startswith(str(self._root)):
            raise ValueError(
                f"StoreKey '{key.value}' resolves outside chat2 root directory"
            )
        return path

    def _ensure_parent(self, path: Path) -> None:
        """Create parent directories if they don't exist."""
        path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Chat2Primitives implementation
    # ------------------------------------------------------------------

    def read_text(self, key: StoreKey) -> Optional[str]:
        path = self._resolve(key)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_text(self, key: StoreKey, text: str) -> None:
        path = self._resolve(key)
        self._ensure_parent(path)
        # Reuse JsonFileStorage's atomic write helper for text files
        self._storage._atomic_write_text(path, text)

    def append_text(self, key: StoreKey, text: str) -> None:
        path = self._resolve(key)
        self._ensure_parent(path)
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)

    def exists(self, key: StoreKey) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: StoreKey) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def list_keys(self, prefix: StoreKey) -> list[StoreKey]:
        base = self._resolve(prefix)
        if not base.exists() or not base.is_dir():
            return []
        keys: list[StoreKey] = []
        for p in base.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self._root)).replace("\\", "/")
                keys.append(StoreKey(rel))
        return keys


__all__ = ["JfsChat2Primitives"]
