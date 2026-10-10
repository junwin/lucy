"""Account-scoped generated text artifacts; never expose arbitrary filesystem paths."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

_ALLOWED = {"yaml": ("application/yaml", ".yaml"), "json": ("application/json", ".json")}


def _dir(config, account_name: str) -> Path:
    if not account_name or account_name in {".", ".."} or "/" in account_name or "\\" in account_name:
        raise ValueError("Invalid account name")
    root = Path(config.get("storage_root_path") or "/home/junwin/lucy_storage")
    ns = config.get("storage_namespace") or "data"
    if not isinstance(ns, str) or not ns or "/" in ns or "\\" in ns or ns in {".", ".."}:
        raise ValueError("Invalid storage namespace")
    return root / ns / "generated_files" / account_name


def save_report(config, account_name: str, content: str, fmt: str):
    if fmt not in _ALLOWED:
        raise ValueError("Unsupported report format")
    folder = _dir(config, account_name)
    folder.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    mime, ext = _ALLOWED[fmt]
    path = folder / f"{file_id}{ext}"
    with path.open("x", encoding="utf-8") as out:
        out.write(content)
    return {"file_id": file_id, "mime_type": mime, "download_name": f"execution-trace-{file_id}{ext}", "size_bytes": path.stat().st_size}


def resolve_report(config, account_name: str, file_id: str):
    try:
        canonical = str(uuid.UUID(str(file_id)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError("Invalid file ID") from exc
    folder = _dir(config, account_name)
    for mime, ext in _ALLOWED.values():
        candidate = folder / (canonical + ext)
        if candidate.is_file() and not candidate.is_symlink():
            return candidate, mime
    raise FileNotFoundError("Report not found for account")
