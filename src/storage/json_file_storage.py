# ==============================================================================
# FILE: src/storage/json_file_storage.py
# JSON-backed storage implementation for Lucy.
# NOTE: contexts are now persisted as Markdown (.md) with YAML frontmatter.
# ==============================================================================

import json
import os
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from src.storage_paths.storage_paths import StoragePaths
from src.tasklists.service import TaskListService


from .base import Storage
from .models import UserProfile
from .json_file_storage_parts.contexts import ContextsMixin
from .json_file_storage_parts.documents import DocumentsMixin
from .json_file_storage_parts.tasklists import DEFAULT_RUN_TTL_DAYS, TasklistsMixin
from .json_file_storage_parts.embeddings import EmbeddingsMixin


class JsonFileStorage(TasklistsMixin, ContextsMixin, DocumentsMixin, EmbeddingsMixin, Storage):
    """JSON-backed storage implementation for Lucy.

    Notes:
      - Contexts were previously stored as JSON files under
        contexts/<account>/<context_id>.json. They are now stored as
        Markdown files (<context_id>.md) with YAML frontmatter. Frontmatter
        keys map onto the persisted Context fields (tag, imports,
        mandatory_tools, search_namespaces, updated_at); unknown keys land
        in Context.extra. The Markdown body is stored in Context.text. The
        Context.updated_at timestamp is taken from the frontmatter
        'updated_at' if present, otherwise from the file's mtime.
    """

    def __init__(
        self,
        storage_paths: StoragePaths,
        tasklist_run_ttl_days: int = DEFAULT_RUN_TTL_DAYS,
    ):

        self.storage_paths = storage_paths
        self._tasklist_service = TaskListService()
        self._tasklist_run_ttl_days = tasklist_run_ttl_days


    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------

    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON atomically.

        Writes to a unique tmp file (uuid4().hex) colocated with the target,
        then atomically replaces the target via os.replace. Unique tmp names
        ensure concurrent writers never collide on a shared tmp path, and
        os.replace is atomic on both Windows and POSIX.
        """
        tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self._atomic_replace(tmp_path, path)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        """Write text (e.g. Markdown) atomically.

        Same unique-tmp + os.replace strategy as _atomic_write.
        """
        tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
        self._atomic_replace(tmp_path, path)

    def _atomic_replace(self, tmp_path: Path, target_path: Path) -> None:
        """Atomically replace target_path with tmp_path.

        Uses os.replace(), which atomically replaces an existing destination on
        both Windows and POSIX. shutil.move() is NOT safe here: on Windows it
        silently falls back to copy2+unlink when the destination exists, which
        is not atomic and can leave a truncated/partial file. tmp is always
        colocated with the target, so a cross-device fallback is unnecessary;
        if one is ever added it must also use unique tmp names.
        """
        try:
            os.replace(tmp_path, target_path)
        except Exception as e:
            logging.error(
                "Atomic replace failed for %s → %s: %s",
                tmp_path, target_path, e,
            )
            try:
                tmp_path.unlink()
            except Exception:
                pass
            raise

    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logging.warning("Failed to decode JSON from %s: %s", path, e)
            return None
        except Exception as e:
            logging.error("Unexpected error reading JSON from %s: %s", path, e)
            return None

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)


    # ----------------------------------------------------------------------
    # USER PROFILES
    # ----------------------------------------------------------------------

    def get_user_profile(self, account_name: str) -> Optional[UserProfile]:
        path = self.storage_paths.users / f"{account_name}.json"
        data = self._load_json(path)
        if not data:
            return None

        return UserProfile(
            account_name=data["account_name"],
            full_name=data.get("full_name"),
            preferences=data.get("preferences", {}),
            active=data.get("active", True),
        )


    # ----------------------------------------------------------------------

    def health_check(self) -> bool:
        try:
            return self.storage_paths.base.exists() and os.access(self.storage_paths.base, os.W_OK)
        except Exception:
            return False
