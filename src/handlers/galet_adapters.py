"""Lucy configuration adapters for galet-tools' narrow handler ports."""

from __future__ import annotations

import os
from typing import Any


class LucyStorageLocationResolver:
    """Resolve Lucy storage and named external roots from ConfigManager."""

    def __init__(self, config: Any) -> None:
        self._config = config

    def storage_base_dir(self) -> str:
        storage_root = (self._config.get("storage_root_path") or "").strip()
        storage_namespace = (
            self._config.get("storage_namespace") or ""
        ).strip()
        if not storage_root:
            raise ValueError("Missing config 'storage_root_path'")
        if not storage_namespace:
            raise ValueError("Missing config 'storage_namespace'")
        return os.path.abspath(
            os.path.join(storage_root, storage_namespace)
        )

    def external_root_dir(self, name: str) -> str:
        roots = self._config.get("external_roots") or {}
        if not isinstance(roots, dict):
            raise ValueError("Config 'external_roots' must be an object/map")
        base = roots.get(name)
        if not base:
            raise ValueError(f"Unknown external_root '{name}'")
        return os.path.abspath(str(base))


class LucySandboxRootResolver:
    """Preserve Lucy's existing account-fenced sandbox resolution."""

    def __init__(self, config: Any) -> None:
        self._config = config

    def sandbox_base_dir(self, *, account_name: str) -> str:
        base = (self._config.get("code_sandbox_path") or "").strip()
        if not base:
            raise ValueError("Missing config 'code_sandbox_path'")
        if os.path.isdir(base):
            base = os.path.join(base, account_name)
        return os.path.abspath(base)


class LucyConfigProvider:
    """Expose the font paths historically used by Lucy's image handler."""

    _DEFAULT_FONT_PATHS = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    )

    def __init__(self, config: Any) -> None:
        self._config = config

    def truetype_font_paths(self) -> list[str]:
        configured = self._config.get("truetype_font_paths")
        if isinstance(configured, (list, tuple)):
            return [str(path) for path in configured]
        return list(self._DEFAULT_FONT_PATHS)
