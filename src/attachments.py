"""Resolve reusable image references from the account-owned conversation."""

import json
import os
import re
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

from src.http_endpoints.upload_endpoints import get_image_download_impl


class ConversationAttachments:
    def __init__(self, config, store):
        self.config = config
        self.store = store

    def images(self, *, account_name, session_id):
        if self.store is None:
            raise ValueError("Conversation storage is unavailable")
        session = self.store.get_session(account_name=account_name, session_id=session_id)
        if session is None or session.account_name != account_name:
            raise ValueError("Conversation not found for this account")
        # Transcript includes archived turns but excludes invalidated exchanges.
        # Image discovery must not depend on the recent-message prompt window.
        snapshot = self.store.get_transcript_snapshot(
            account_name=account_name, session_id=session_id,
        )
        references = []
        seen = set()
        last_videos = {}
        for event in reversed(snapshot.events):
            if event.kind == "generated_video" and isinstance(event.content, dict):
                source = event.content.get("source_image_id")
                if isinstance(source, str) and source not in last_videos:
                    last_videos[source] = event.content.get("video_id")
                continue
            if event.kind == "user_message":
                ids = (event.metadata or {}).get("image_ids", [])
                origin = "uploaded"
            elif event.kind == "generated_image" and isinstance(event.content, dict):
                ids = [event.content.get("image_id")]
                origin = "generated"
            else:
                continue
            if not isinstance(ids, (list, tuple)):
                continue
            for position, image_id in enumerate(ids, 1):
                if not isinstance(image_id, str) or image_id in seen:
                    continue
                path, body, status = get_image_download_impl(self.config, account_name, image_id)
                if status != 200:
                    continue
                image_id = body["id"]
                if image_id in seen:
                    continue
                seen.add(image_id)
                metadata_path = Path(path).with_suffix(".json")
                with metadata_path.open(encoding="utf-8") as handle:
                    metadata = json.load(handle)
                references.append({
                    "image_id": image_id,
                    "filename": str(metadata.get("original_filename") or Path(path).name)[:200],
                    "mime_type": body["mime_type"],
                    "origin": origin,
                    "event_id": event.event_id,
                    "correlation_ids": list(event.correlation_ids),
                    "position": position,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                    "size_bytes": metadata.get("size_bytes"),
                    "preview_url": f"/download/image/{image_id}?accountName={quote(account_name, safe='')}",
                    "path": f"images/{account_name}/{Path(path).name}",
                })
        for reference in references:
            reference["last_video_id"] = last_videos.get(reference["image_id"])
        return references


# Aliases are configured locally, not selected as arbitrary file paths by agents.
# The account and conversation membership is checked before a file is copied.
_ALLOWED_EXPORT_MIME = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _safe_upload_name(filename, image_id, extension):
    """Preserve a readable basename without allowing traversal or hidden paths."""
    original = str(filename or "").replace(chr(92), "/").split("/")[-1]
    stem = Path(original).stem
    stem = re.sub(r"[^A-Za-z0-9 _.-]", "-", stem).strip(" .-_")[:90]
    if not stem or stem in {".", ".."}:
        stem = image_id
    return stem + extension


def _export_root(config, external_root, relative_path):
    """Resolve a destination through Lucy's existing approved external roots."""
    from src.handlers.galet_adapters import LucyStorageLocationResolver

    if not isinstance(external_root, str) or not external_root:
        raise ValueError("external_root must name an approved root")
    if not isinstance(relative_path, str):
        raise ValueError("relative_path must be a string")
    if not relative_path or relative_path in (".", ".."):
        raise ValueError("Supply a nonempty subfolder relative to external_root")
    if os.path.isabs(relative_path) or chr(92) in relative_path:
        raise ValueError("relative_path must use root-relative POSIX separators")
    parts = Path(relative_path).parts
    if ".." in parts or "." in parts:
        raise ValueError("relative_path cannot contain traversal components")

    base = Path(LucyStorageLocationResolver(config).external_root_dir(external_root)).resolve()
    destination = (base / relative_path).resolve()
    if not destination.is_relative_to(base) or destination == base:
        raise ValueError("Export destination must be inside the approved external root")
    if destination.exists() and not destination.is_dir():
        raise ValueError("Export destination is not a directory")
    return destination



def export_conversation_images(config, store, *, account_name, session_id,
                               image_ids, external_root, relative_path, collision="rename"):
    """Copy owned chat images to a fresh, isolated batch under an approved root.

    Uses exclusive file creation to avoid overwrites, and cleans up partially
    created batches on error. Existing uploads are always retained.
    """
    if not isinstance(image_ids, list) or not 1 <= len(image_ids) <= 20:
        raise ValueError("Supply 1-20 image IDs")
    if not all(isinstance(i, str) and i for i in image_ids):
        raise ValueError("Image IDs must be nonempty strings")
    if len(image_ids) != len(set(image_ids)):
        raise ValueError("Image IDs must be unique")
    if collision not in ("rename", "fail"):
        raise ValueError("collision must be rename or fail")
    references = ConversationAttachments(config, store).images(
        account_name=account_name, session_id=session_id
    )
    by_id = {item["image_id"]: item for item in references}
    if any(image_id not in by_id for image_id in image_ids):
        raise ValueError("One or more images are not available in this conversation")
    root = _export_root(config, external_root, relative_path)

    # Resolve and check *every* file before creating output.
    planned = []
    for image_id in image_ids:
        reference = by_id[image_id]
        mime = reference["mime_type"]
        if mime not in _ALLOWED_EXPORT_MIME:
            raise ValueError(f"Image {image_id} type is not supported for export")
        source, _, status = get_image_download_impl(config, account_name, image_id)
        if status != 200:
            raise ValueError(f"Image {image_id} could not be loaded")
        source = Path(source).resolve(strict=True)
        if not source.is_file():
            raise ValueError(f"Image {image_id} is missing")
        planned.append((image_id, source, _safe_upload_name(
            reference["filename"], image_id, _ALLOWED_EXPORT_MIME[mime]
        )))

    from src.handlers.galet_adapters import LucyStorageLocationResolver

    # UUID directory name ensures two concurrent exports do not share files.
    root.mkdir(parents=True, exist_ok=True)
    batch = root / ("batch-" + uuid.uuid4().hex[:12])
    batch.mkdir(mode=0o700)
    exported = []
    used_names = set()
    try:
        for position, (image_id, source, original_name) in enumerate(planned, 1):
            filename = original_name
            if filename.casefold() in used_names:
                if collision == "fail":
                    raise ValueError(f"Duplicate original filename: {filename}")
                filename = f"{Path(filename).stem}-{image_id[:8]}{Path(filename).suffix}"
            used_names.add(filename.casefold())
            target = batch / filename
            with source.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
            exported.append({
                "image_id": image_id,
                "filename": filename,
                "path": str(target),
                "position": position,
            })
        return {"external_root": external_root, "relative_path": relative_path,
                "batch_relative_path": str(batch.relative_to(Path(LucyStorageLocationResolver(config).external_root_dir(external_root)).resolve())),
                "batch_directory": str(batch),
                "exported": exported, "count": len(exported)}
    except Exception:
        shutil.rmtree(batch)
        raise
