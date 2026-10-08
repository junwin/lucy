import json
import os
from uuid import uuid4

from src.handlers.serve_video_handler import ServeVideoHandler
from src.message_processors.fcp_loop import LLMLoopRunner


class Config:
    def __init__(self, root):
        self.values = {"storage_root_path": str(root), "storage_namespace": "data"}

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_serve_video_emits_browser_video_event(tmp_path):
    config = Config(tmp_path)
    video_id = str(uuid4())
    directory = tmp_path / "data" / "videos" / "john"
    directory.mkdir(parents=True)
    (directory / f"{video_id}.mp4").write_bytes(b"mp4")

    result = ServeVideoHandler(config).execute(
        {"video_id": video_id}, account_name="john"
    )

    assert result["ok"] is True
    assert result["video"] == {
        "url": f"/download/video/{video_id}?accountName=john",
        "mime_type": "video/mp4",
        "download_name": f"{video_id}.mp4",
        "video_id": video_id,
    }
    events = list(LLMLoopRunner._inspect_raw_results([
        (object(), json.dumps(result)),
    ]))
    assert len(events) == 1
    assert events[0].type == "video"
    assert events[0].video_url == result["video"]["url"]
    assert events[0].video_id == video_id


def test_serve_video_rejects_other_accounts_video(tmp_path):
    config = Config(tmp_path)
    video_id = str(uuid4())
    directory = tmp_path / "data" / "videos" / "john"
    directory.mkdir(parents=True)
    (directory / f"{video_id}.mp4").write_bytes(b"mp4")

    result = ServeVideoHandler(config).execute(
        {"video_id": video_id}, account_name="arla"
    )

    assert result["ok"] is False
    assert result["error"] == "Video not found"


def test_serve_video_rejects_invalid_video_id(tmp_path):
    result = ServeVideoHandler(Config(tmp_path)).execute(
        {"video_id": "../secret"}, account_name="john"
    )

    assert result["ok"] is False
    assert "UUID" in result["error"]
