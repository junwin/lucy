"""Resolve image references and read previews at Lucy's delivery boundary."""

import base64
import io
import mimetypes
import os
from pathlib import Path

from PIL import Image

from src.handlers.galet_adapters import LucyStorageLocationResolver
from src.http_endpoints.upload_endpoints import get_image_download_impl

DEFAULT_MAX_DIMENSION = 1024
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp",
    "image/svg+xml", "image/tiff",
}


class ImagePresentationService:
    def __init__(self, config):
        self.config = config

    def resolve(self, reference, account_name):
        """Resolve UUIDs within the current account, or validated serving paths."""
        if reference.get("image_id"):
            path, metadata, status = get_image_download_impl(
                self.config, account_name, reference["image_id"]
            )
            if status != 200:
                raise ValueError(metadata["error"])
            return path, metadata["mime_type"]

        path = reference.get("path", "")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path is required")
        path = path.strip()
        path = path.replace("\\", "/")
        parts = [part for part in path.split("/") if part not in ("", ".")]
        if os.path.isabs(path) or (len(path) >= 2 and path[1] == ":"):
            raise ValueError("path must be relative, not absolute")
        if ".." in parts or os.path.normpath(path) in ("", ".", ".."):
            raise ValueError("path must not contain '..' segments")

        resolver = LucyStorageLocationResolver(self.config)
        location = reference.get("location", "storage")
        if location == "storage":
            base = resolver.storage_base_dir()
            # Account-owned image files must go through their UUID metadata.
            if parts[0] == "images":
                if len(parts) != 3 or parts[1] != account_name:
                    raise ValueError("Image unavailable for this account")
                return self.resolve({"image_id": Path(parts[2]).stem}, account_name)
        elif location == "external":
            root = reference.get("external_root", "")
            if not root:
                raise ValueError("external_root is required when location='external'")
            base = resolver.external_root_dir(root)
        else:
            raise ValueError(f"Unknown location '{location}'")
        base = os.path.realpath(base)
        full = os.path.realpath(os.path.join(base, path))
        if os.path.commonpath([base, full]) != base:
            raise ValueError("File access outside allowed base path")
        if not os.path.isfile(full):
            raise ValueError(f"Image not found: {path}")
        mime = mimetypes.guess_type(full)[0]
        if mime not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Unsupported image type: {mime or 'unknown'}")
        return full, mime

    def preview(self, reference, account_name):
        """Read and encode only for the browser; never include bytes in tool results."""
        path, mime = self.resolve(reference, account_name)
        max_dim = reference.get("max_dimension", DEFAULT_MAX_DIMENSION)
        if not isinstance(max_dim, int) or isinstance(max_dim, bool) or max_dim <= 0:
            raise ValueError("max_dimension must be a positive integer")
        max_dim = min(max_dim, DEFAULT_MAX_DIMENSION)
        raw = Path(path).read_bytes()
        if mime != "image/svg+xml":
            with Image.open(io.BytesIO(raw)) as source:
                if max(source.size) > max_dim:
                    fmt = source.format or "PNG"
                    source.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    source.save(output, format=fmt)
                    raw = output.getvalue()
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
