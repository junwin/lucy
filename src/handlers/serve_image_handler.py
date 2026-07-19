"""ServeImageHandler — reads an image file from disk and returns it as base64.

When the LLM calls serve_image, this handler reads a binary image file from
the requested location, detects its MIME type, base64-encodes it, and returns
it as a data URI. The FCP streaming loop detects the "image" key and emits
an SSE image event for the client to render.

Images are automatically downscaled if they exceed max_dimension on the
longest side (default 512) to keep base64 payloads under tool-result limits.
"""

from __future__ import annotations

import base64
import io
import logging
import mimetypes
import os
from typing import Any, Dict, Tuple

from PIL import Image

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2

logger = logging.getLogger(__name__)

# Whitelist of MIME types we allow serving
_ALLOWED_MIME_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/bmp",
    "image/svg+xml",
    "image/tiff",
})

# Map common extensions that mimetypes might not know
_EXTENSION_OVERRIDES: Dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

_DEFAULT_MAX_DIMENSION = 512


def _downscale_if_needed(raw_bytes: bytes, mime: str, max_dim: int) -> bytes:
    """If the image exceeds max_dim on its longest side, downscale it.

    Returns the (possibly resized) image bytes in the original format.
    SVG images are returned as-is (vector, no dimensions to check).
    """
    if mime == "image/svg+xml":
        return raw_bytes

    try:
        img = Image.open(io.BytesIO(raw_bytes))
    except Exception:
        logger.warning("serve_image: PIL cannot open image, returning as-is")
        return raw_bytes

    longest = max(img.size)
    if longest <= max_dim:
        return raw_bytes

    scale = max_dim / longest
    new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
    logger.info("serve_image: downscaling %s -> %s", img.size, new_size)

    out_buf = io.BytesIO()
    # Preserve format; default to JPEG for unknown/raw modes
    fmt = img.format or "JPEG"
    save_kwargs: Dict[str, Any] = {}
    if fmt == "JPEG":
        save_kwargs["quality"] = 85
        save_kwargs["optimize"] = True
    img = img.resize(new_size, Image.LANCZOS)
    img.save(out_buf, format=fmt, **save_kwargs)
    return out_buf.getvalue()


class ServeImageHandler(HandlerV2):
    """Handler that reads an image file and returns it as a base64 data URI."""

    NAME = "serve_image"

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "REQUIRED — when the user asks to see, show, or display a specific "
                "image file, you MUST call this tool immediately. Do not ask clarifying "
                "questions about where or how to display it. Reads an image file from "
                "disk and returns it as a base64-encoded data URI for display."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "enum": ["storage", "external"],
                        "description": "Where to load from.",
                    },
                    "external_root": {
                        "type": "string",
                        "description": "Named external root key when location='external'. Use '' otherwise.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Relative path to the image file under the chosen location (no leading /, no ..).",
                    },
                    "max_dimension": {
                        "type": "integer",
                        "description": (
                            "Maximum size in pixels for the longest side. "
                            "Images larger than this are downscaled before encoding. "
                            f"Default is {_DEFAULT_MAX_DIMENSION}."
                        ),
                    },
                },
                "required": ["location", "external_root", "path"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "alt": {"type": "string"},
                    },
                    "required": ["url", "alt"],
                    "additionalProperties": False,
                },
                "ok": {"type": "boolean"},
            },
            "required": ["image", "ok"],
            "additionalProperties": False,
        }

    # ------------------------------------------------------------------
    # HandlerV2 interface
    # ------------------------------------------------------------------

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context) -> Dict[str, Any]:
        path_in = (args.get("path") or "").strip()
        location = (args.get("location") or "storage").strip().lower()
        external_root = (args.get("external_root") or "").strip()
        max_dimension = args.get("max_dimension", _DEFAULT_MAX_DIMENSION)

        if not path_in:
            return {
                "ok": False,
                "error": "path is required",
            }

        # Validate and normalize relative path
        norm_rel, err = self._validate_and_normalize_relative_path(path_in)
        if err:
            return {"ok": False, "error": err, "path": path_in}

        # Determine base directory
        try:
            if location == "storage":
                base_dir = self._storage_base_dir()
            elif location == "external":
                if not external_root:
                    return {
                        "ok": False,
                        "error": "external_root is required when location='external'",
                    }
                base_dir = self._external_root_dir(external_root)
            else:
                return {"ok": False, "error": f"Unknown location '{location}'"}
        except Exception as e:
            logger.exception("serve_image: failed to resolve base directory")
            return {"ok": False, "error": str(e)}

        logger.info(
            "serve_image: account=%s location=%s external_root=%s path=%s max_dim=%s",
            account_name,
            location,
            external_root,
            path_in,
            max_dimension,
        )

        # Resolve full path with containment check
        base_abs = os.path.abspath(base_dir)
        full_path = os.path.normpath(os.path.join(base_abs, norm_rel))

        base_real = os.path.realpath(base_abs)
        full_real = os.path.realpath(full_path)

        if not (full_real == base_real or full_real.startswith(base_real + os.path.sep)):
            return {"ok": False, "error": "File access outside allowed base path"}

        if not os.path.isfile(full_real):
            return {"ok": False, "error": f"Image not found: {path_in}"}

        # Detect MIME type
        ext = os.path.splitext(full_real)[1].lower()
        mime = _EXTENSION_OVERRIDES.get(ext)
        if mime is None:
            mime, _ = mimetypes.guess_type(full_real)
        if not mime or mime not in _ALLOWED_MIME_TYPES:
            return {
                "ok": False,
                "error": (
                    f"Unsupported image type: {mime or 'unknown'} (ext: {ext}). "
                    "Supported: jpeg, png, gif, webp, bmp, svg, tiff."
                ),
            }

        # Read
        try:
            with open(full_real, "rb") as f:
                raw_bytes = f.read()
        except Exception as e:
            logger.exception("serve_image: failed to read file")
            return {"ok": False, "error": f"Failed to read file: {e}"}

        # Downscale if needed
        raw_bytes = _downscale_if_needed(raw_bytes, mime, max_dimension)

        # Encode
        b64 = base64.b64encode(raw_bytes).decode("ascii")
        file_name = os.path.basename(norm_rel)

        return {
            "ok": True,
            "image": {
                "url": f"data:{mime};base64,{b64}",
                "alt": file_name,
            },
        }

    # ------------------------------------------------------------------
    # Resolution helpers (same logic as FileLoadHandler2)
    # ------------------------------------------------------------------

    def _storage_base_dir(self) -> str:
        storage_root = (self.config.get("storage_root_path") or "").strip()
        storage_ns = (self.config.get("storage_namespace") or "").strip()
        if not storage_root:
            raise ValueError("Missing config 'storage_root_path'")
        if not storage_ns:
            raise ValueError("Missing config 'storage_namespace'")
        base = os.path.join(storage_root, storage_ns)
        return os.path.abspath(base)

    def _external_root_dir(self, external_root: str) -> str:
        roots = self.config.get("external_roots") or {}
        if not isinstance(roots, dict):
            raise ValueError("Config 'external_roots' must be an object/map")
        base = roots.get(external_root)
        if not base:
            raise ValueError(f"Unknown external_root '{external_root}'")
        return os.path.abspath(str(base))

    # ------------------------------------------------------------------
    # Path validation
    # ------------------------------------------------------------------

    @staticmethod
    def _has_drive_letter(path: str) -> bool:
        return len(path) >= 2 and path[1] == ":" and path[0].isalpha()

    def _validate_and_normalize_relative_path(self, path_in: str) -> Tuple[str, str]:
        if self._has_drive_letter(path_in):
            return "", "path must be relative, not include drive letters"
        if os.path.isabs(path_in):
            return "", "path must be relative, not absolute"

        norm_rel = os.path.normpath(path_in)

        if norm_rel in ("", ".", ".."):
            return "", "path must not be empty or point to current/parent directory"

        parts = [p for p in norm_rel.split(os.path.sep) if p]
        if os.path.altsep:
            parts = [p for seg in parts for p in seg.split(os.path.altsep) if p]
        if any(p == ".." for p in parts) or norm_rel.startswith(".."):
            return "", "path must not contain '..' segments"

        return norm_rel, ""
