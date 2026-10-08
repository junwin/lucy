"""Resolve MP4 files and build browser-safe video delivery URLs."""

import mimetypes
import os
from pathlib import Path
from urllib.parse import urlencode

from src.handlers.galet_adapters import LucyStorageLocationResolver
from src.http_endpoints.upload_endpoints import get_video_download_impl


class VideoPresentationService:
    """Resolve generated videos or relative MP4 paths under configured roots."""

    def __init__(self, config):
        self.config = config

    def resolve(self, reference, account_name):
        video_id = (reference.get("video_id") or "").strip()
        if video_id:
            path, metadata, status = get_video_download_impl(
                self.config, account_name, video_id
            )
            if status != 200 or path is None:
                raise ValueError(metadata.get("error", "Video is unavailable"))
            normalized_id = metadata["id"]
            return path, "video/mp4", {
                "video_id": normalized_id,
                "url": f"/download/video/{normalized_id}?{urlencode({'accountName': account_name})}",
                "download_name": f"{normalized_id}.mp4",
            }

        raw_path = reference.get("path", "")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("path is required")
        normalized_path = raw_path.strip().replace("\\", "/")
        parts = [part for part in normalized_path.split("/") if part not in ("", ".")]
        if os.path.isabs(normalized_path) or (len(normalized_path) >= 2 and normalized_path[1] == ":"):
            raise ValueError("path must be relative, not absolute")
        if ".." in parts or os.path.normpath(normalized_path) in ("", ".", ".."):
            raise ValueError("path must not contain '..' segments")

        resolver = LucyStorageLocationResolver(self.config)
        location = (reference.get("location") or "storage").strip().lower()
        if location == "storage":
            base = resolver.storage_base_dir()
            if parts[0] == "videos":
                if len(parts) < 3 or parts[1] != account_name:
                    raise ValueError("Video unavailable for this account")
        elif location == "external":
            root = (reference.get("external_root") or "").strip()
            if not root:
                raise ValueError("external_root is required when location='external'")
            base = resolver.external_root_dir(root)
        else:
            raise ValueError(f"Unknown location '{location}'")

        base = os.path.realpath(base)
        path = os.path.realpath(os.path.join(base, normalized_path))
        if os.path.commonpath([base, path]) != base:
            raise ValueError("File access outside allowed base path")
        if not os.path.isfile(path):
            raise ValueError(f"Video not found: {normalized_path}")
        mime_type = mimetypes.guess_type(path)[0]
        if mime_type != "video/mp4":
            raise ValueError(f"Unsupported video type: {mime_type or 'unknown'}")

        query = urlencode({
            "accountName": account_name,
            "location": location,
            "external_root": (reference.get("external_root") or "").strip(),
            "path": normalized_path,
        })
        return path, mime_type, {
            "video_id": None,
            "url": f"/stream/video?{query}",
            "download_name": Path(path).name,
        }

    def resolve_stream_request(self, *, account_name, location, external_root, path):
        return self.resolve({
            "location": location,
            "external_root": external_root,
            "path": path,
        }, account_name)
