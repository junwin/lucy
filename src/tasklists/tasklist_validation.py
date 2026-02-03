"""Tasklist validation + canonicalization helpers.

This module is the storage boundary for tasklist CRUD.

Rules (Span 1):
- tasklist_id must be safe for use as a filename (no separators, no traversal)
- payload may omit 'id' (it will be injected)
- if payload includes 'id', it must match tasklist_id
- ensure 'tasks' exists and is a list (default [])
- ensure 'schema_version' exists (default 1)

These helpers are intentionally small and dependency-free so they can be used
from storage and/or HTTP boundary code.
"""

from __future__ import annotations

import re
from typing import Any, Dict


_VALID_TASKLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_tasklist_id(tasklist_id: str) -> None:
    if not isinstance(tasklist_id, str) or not tasklist_id:
        raise ValueError("tasklist_id must be a non-empty string")
    if "/" in tasklist_id or "\\" in tasklist_id:
        raise ValueError("tasklist_id must not contain path separators")
    if tasklist_id in (".", ".."):
        raise ValueError("invalid tasklist_id")
    if not _VALID_TASKLIST_ID_RE.fullmatch(tasklist_id):
        raise ValueError("tasklist_id contains invalid characters")


def canonicalize_tasklist_dict(tasklist_id: str, d: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonicalized copy of the tasklist dict.

    Raises ValueError on invalid input.
    """
    validate_tasklist_id(tasklist_id)
    if not isinstance(d, dict):
        raise ValueError("tasklist must be a dict")

    out: Dict[str, Any] = dict(d)

    if "id" in out and out["id"] != tasklist_id:
        raise ValueError("tasklist id mismatch between path and payload")
    out["id"] = tasklist_id

    if "schema_version" not in out:
        out["schema_version"] = 1

    if "tasks" not in out:
        out["tasks"] = []
    if not isinstance(out["tasks"], list):
        raise ValueError("tasks must be a list")

    return out
