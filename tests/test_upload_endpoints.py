"""Tests for upload_endpoints.py — POST /upload/image."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, Dict

import pytest

# Ensure repo root is on path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.http_endpoints.upload_endpoints import (
    get_video_download_impl,
    post_upload_image_impl,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(overrides: Dict[str, Any] = None) -> Any:
    """Return a simple config-like object with get()."""
    class FakeConfig:
        def __init__(self, values: Dict[str, Any]):
            self.values = values
        def get(self, key: str, default: Any = None) -> Any:
            return self.values.get(key, default)
    values = {
        "storage_root_path": tempfile.mkdtemp(),
        "storage_namespace": "data",
        "max_upload_size_bytes": 10 * 1024 * 1024,
    }
    if overrides:
        values.update(overrides)
    return FakeConfig(values)


def _make_png_bytes() -> bytes:
    """Return minimal PNG file bytes (not valid PNG, just for testing)."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _make_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _make_gif_bytes() -> bytes:
    return b"GIF89a" + b"\x00" * 100


def _make_webp_bytes() -> bytes:
    return b"RIFF" + b"\x00" * 100 + b"WEBP"


# ---------------------------------------------------------------------------
# Tests: success cases
# ---------------------------------------------------------------------------


def test_upload_png_success():
    config = _make_config()
    file_data = _make_png_bytes()

    body, status = post_upload_image_impl(
        config=config,
        account_name="junwin",
        file_data=file_data,
        original_filename="screenshot.png",
        mime_type="image/png",
    )

    assert status == 200
    assert body["ok"] is True
    assert body["filename"] == "screenshot.png"
    assert body["mime_type"] == "image/png"
    assert len(body["id"]) == 36  # UUID

    # Verify file was written
    base_dir = os.path.join(config.get("storage_root_path"), "data", "images", "junwin")
    img_id = body["id"]
    assert os.path.exists(os.path.join(base_dir, f"{img_id}.png"))
    assert os.path.exists(os.path.join(base_dir, f"{img_id}.json"))

    # Verify metadata
    with open(os.path.join(base_dir, f"{img_id}.json")) as f:
        meta = json.load(f)
    assert meta["id"] == img_id
    assert meta["account"] == "junwin"
    assert meta["original_filename"] == "screenshot.png"
    assert meta["mime_type"] == "image/png"
    assert meta["size_bytes"] == len(file_data)
    assert "uploaded_at" in meta


def test_upload_jpeg_success():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="junwin",
        file_data=_make_jpeg_bytes(),
        original_filename="photo.jpg",
        mime_type="image/jpeg",
    )
    assert status == 200
    assert body["mime_type"] == "image/jpeg"
    # Verify .jpg extension
    base = os.path.join(config.get("storage_root_path"), "data", "images", "junwin")
    assert os.path.exists(os.path.join(base, f"{body['id']}.jpg"))


def test_upload_gif_success():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="john",
        file_data=_make_gif_bytes(),
        original_filename="anim.gif",
        mime_type="image/gif",
    )
    assert status == 200
    assert body["mime_type"] == "image/gif"


def test_upload_webp_success():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="test",
        file_data=_make_webp_bytes(),
        original_filename="img.webp",
        mime_type="image/webp",
    )
    assert status == 200
    assert body["mime_type"] == "image/webp"


def test_upload_unique_ids():
    """Two uploads get different IDs."""
    config = _make_config()
    body1, _ = post_upload_image_impl(
        config=config,
        account_name="a",
        file_data=_make_png_bytes(),
        original_filename="1.png",
        mime_type="image/png",
    )
    body2, _ = post_upload_image_impl(
        config=config,
        account_name="a",
        file_data=_make_png_bytes(),
        original_filename="2.png",
        mime_type="image/png",
    )
    assert body1["id"] != body2["id"]


def test_upload_different_accounts_separated():
    """Uploads for different accounts go to different directories."""
    config = _make_config()
    body1, _ = post_upload_image_impl(
        config=config,
        account_name="alice",
        file_data=_make_png_bytes(),
        original_filename="a.png",
        mime_type="image/png",
    )
    body2, _ = post_upload_image_impl(
        config=config,
        account_name="bob",
        file_data=_make_png_bytes(),
        original_filename="b.png",
        mime_type="image/png",
    )

    base = os.path.join(config.get("storage_root_path"), "data", "images")
    assert os.path.exists(os.path.join(base, "alice", f"{body1['id']}.png"))
    assert os.path.exists(os.path.join(base, "bob", f"{body2['id']}.png"))


# ---------------------------------------------------------------------------
# Tests: validation errors
# ---------------------------------------------------------------------------


def test_missing_account_name():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="",
        file_data=_make_png_bytes(),
        original_filename="x.png",
        mime_type="image/png",
    )
    assert status == 400
    assert "error" in body


def test_empty_file_data():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="junwin",
        file_data=b"",
        original_filename="x.png",
        mime_type="image/png",
    )
    assert status == 400
    assert "error" in body


def test_invalid_mime_type():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="junwin",
        file_data=_make_png_bytes(),
        original_filename="x.pdf",
        mime_type="application/pdf",
    )
    assert status == 400
    assert "Unsupported image type" in body["error"]


def test_file_too_large():
    config = _make_config({"max_upload_size_bytes": 100})
    body, status = post_upload_image_impl(
        config=config,
        account_name="junwin",
        file_data=b"x" * 200,
        original_filename="big.png",
        mime_type="image/png",
    )
    assert status == 413
    assert "File too large" in body["error"]



def test_video_download_resolves_account_owned_file():
    config = _make_config()
    video_id = str(__import__("uuid").uuid4())
    directory = os.path.join(
        config.get("storage_root_path"), "data", "videos", "arla"
    )
    os.makedirs(directory)
    expected = os.path.join(directory, f"{video_id}.mp4")
    with open(expected, "wb") as handle:
        handle.write(b"video-data")

    path, body, status = get_video_download_impl(config, "arla", video_id)

    assert status == 200
    assert body == {"ok": True, "id": video_id}
    assert path == expected


def test_video_download_is_account_scoped():
    config = _make_config()
    video_id = str(__import__("uuid").uuid4())
    directory = os.path.join(
        config.get("storage_root_path"), "data", "videos", "john"
    )
    os.makedirs(directory)
    with open(os.path.join(directory, f"{video_id}.mp4"), "wb") as handle:
        handle.write(b"video-data")

    path, body, status = get_video_download_impl(config, "arla", video_id)

    assert path is None
    assert status == 404
    assert body["error"] == "Video not found"


def test_video_download_rejects_invalid_id():
    config = _make_config()

    path, body, status = get_video_download_impl(config, "arla", "../secret")

    assert path is None
    assert status == 400
    assert "UUID" in body["error"]


def test_upload_rejects_path_like_account_name():
    config = _make_config()
    body, status = post_upload_image_impl(
        config=config,
        account_name="../arla",
        file_data=_make_png_bytes(),
        original_filename="x.png",
        mime_type="image/png",
    )

    assert status == 400
    assert "accountName" in body["error"]
