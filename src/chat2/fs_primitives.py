"""
Filesystem adapter for Chat v2 storage primitives.

Maps StoreKey logical paths to real filesystem paths under a root directory.
Implements Chat2Primitives using pathlib.Path.

This is one implementation of the primitives interface — not part of the
storage-facing API. Used for tests (tmp_path) and early integration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.chat2.store_primitives import Chat2Primitives, StoreKey


class FileChat2Primitives:
    """Filesystem-backed implementation of Chat2Primitives.

    Maps each StoreKey to a file at ``root_dir / key.value``.
    Creates parent directories as needed on write/append.

    Args:
        root_dir: The root directory under which all keys are stored.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self._root = Path(root_dir).resolve()

    def _resolve(self, key: StoreKey) -> Path:
        """Resolve a StoreKey to an absolute filesystem path.

        Security: ensures the resolved path stays within root_dir.
        """
        path = (self._root / key.value).resolve()
        if not str(path).startswith(str(self._root)):
            raise ValueError(
                f"StoreKey '{key.value}' resolves outside root directory"
            )
        return path

    def read_text(self, key: StoreKey) -> Optional[str]:
        path = self._resolve(key)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write_text(self, key: StoreKey, text: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def append_text(self, key: StoreKey, text: str) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
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
        # Collect all files under the prefix directory
        keys: list[StoreKey] = []
        for path in base.rglob("*"):
            if path.is_file():
                rel = path.relative_to(self._root)
                keys.append(StoreKey(str(rel)))
        return keys


__all__ = ["FileChat2Primitives"]
