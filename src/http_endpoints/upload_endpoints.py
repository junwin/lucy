"""HTTP endpoint implementations for image/file uploads.

Step 1 (images): POST /upload/image — accepts multipart file, saves to
lucy_data_files/data/images/{account}/{uuid}.{ext} with metadata sidecar.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from src.config_manager import ConfigManager

ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

EXT_BY_MIME: Dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

logger = logging.getLogger(__name__)


def _build_image_dir(config: ConfigManager, account_name: str) -> str:
    storage_root = config.get("storage_root_path", "/home/junwin/lucy_storage")
    storage_ns = config.get("storage_namespace", "data")
    return os.path.join(storage_root, storage_ns, "images", account_name)


def post_upload_image_impl(
    config: ConfigManager,
    account_name: str,
    file_data: bytes,
    original_filename: str,
    mime_type: str,
) -> Tuple[Dict[str, Any], int]:
    """Save an uploaded image and return its ID + metadata.

    Returns (body_dict, http_status).
    """

    # --- Validation ----------------------------------------------------------

    if not account_name:
        return {"error": "accountName is required"}, 400

    if not file_data:
        return {"error": "No file data provided"}, 400

    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
        return {
            "error": f"Unsupported image type: {mime_type}. Allowed: {allowed}"
        }, 400

    max_size: int = config.get("max_upload_size_bytes", 10 * 1024 * 1024)
    if len(file_data) > max_size:
        mb = max_size // (1024 * 1024)
        return {"error": f"File too large. Maximum size: {mb} MB"}, 413

    # --- Persist -------------------------------------------------------------

    img_id = str(uuid.uuid4())
    ext = EXT_BY_MIME.get(mime_type, ".bin")

    base_dir = _build_image_dir(config, account_name)
    os.makedirs(base_dir, exist_ok=True)

    img_path = os.path.join(base_dir, f"{img_id}{ext}")
    meta_path = os.path.join(base_dir, f"{img_id}.json")

    with open(img_path, "wb") as f:
        f.write(file_data)

    metadata: Dict[str, Any] = {
        "id": img_id,
        "account": account_name,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "size_bytes": len(file_data),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        "upload/image: id=%s account=%s filename=%s size=%d mime=%s",
        img_id,
        account_name,
        original_filename,
        len(file_data),
        mime_type,
    )

    return {
        "ok": True,
        "id": img_id,
        "filename": original_filename,
        "mime_type": mime_type,
    }, 200
