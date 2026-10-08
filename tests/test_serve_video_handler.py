import json
from uuid import uuid4

from src.handlers.serve_video_handler import ServeVideoHandler
from src.message_processors.fcp_loop import LLMLoopRunner


class Config:
    def __init__(self, root):
        self.values = {
            "storage_root_path": str(root),
            "storage_namespace": "data",
            "external_roots": {"media": str(root / "external")},
        }

    def get(self, key, default=None):
        return self.values.get(key, default)


def args(*, video_id="", location="storage", external_root="", path=""):
    return {
        "video_id": video_id,
        "location": location,
        "external_root": external_root,
        "path": path,
    }


def test_serve_generated_video_uses_existing_video_event(tmp_path):
    config = Config(tmp_path)
    video_id = str(uuid4())
    directory = tmp_path / "data" / "videos" / "john"
    directory.mkdir(parents=True)
    (directory / f"{video_id}.mp4").write_bytes(b"mp4")

    result = ServeVideoHandler(config).execute(
        args(video_id=video_id), account_name="john"
    )

    assert result["ok"] is True
    assert result["video"] == {
        "url": f"/download/video/{video_id}?accountName=john",
        "mime_type": "video/mp4",
        "download_name": f"{video_id}.mp4",
        "video_id": video_id,
    }
    events = list(LLMLoopRunner._inspect_raw_results([(object(), json.dumps(result))]))
    assert len(events) == 1
    assert events[0].type == "video"
    assert events[0].video_url == result["video"]["url"]
    assert events[0].video_id == video_id


def test_serve_storage_mp4_returns_browser_stream_url(tmp_path):
    config = Config(tmp_path)
    directory = tmp_path / "data" / "clips"
    directory.mkdir(parents=True)
    (directory / "reel.mp4").write_bytes(b"mp4")

    result = ServeVideoHandler(config).execute(
        args(path="clips/reel.mp4"), account_name="john"
    )

    assert result["ok"] is True
    video = result["video"]
    assert video["url"].startswith("/stream/video?")
    assert "accountName=john" in video["url"]
    assert "path=clips%2Freel.mp4" in video["url"]
    assert video["mime_type"] == "video/mp4"
    assert video["download_name"] == "reel.mp4"
    assert video["video_id"] is None


def test_serve_video_rejects_other_accounts_video(tmp_path):
    config = Config(tmp_path)
    video_id = str(uuid4())
    directory = tmp_path / "data" / "videos" / "john"
    directory.mkdir(parents=True)
    (directory / f"{video_id}.mp4").write_bytes(b"mp4")

    result = ServeVideoHandler(config).execute(
        args(video_id=video_id), account_name="arla"
    )

    assert result["ok"] is False
    assert result["error"] == "Video not found"


def test_serve_video_rejects_invalid_video_id_and_path(tmp_path):
    handler = ServeVideoHandler(Config(tmp_path))

    invalid_id = handler.execute(args(video_id="../secret"), account_name="john")
    traversal = handler.execute(args(path="../secret.mp4"), account_name="john")

    assert invalid_id["ok"] is False
    assert "UUID" in invalid_id["error"]
    assert traversal["ok"] is False
    assert "path" in traversal["error"]


def test_serve_video_rejects_non_mp4_file(tmp_path):
    config = Config(tmp_path)
    directory = tmp_path / "data" / "clips"
    directory.mkdir(parents=True)
    (directory / "clip.avi").write_bytes(b"video")

    result = ServeVideoHandler(config).execute(
        args(path="clips/clip.avi"), account_name="john"
    )

    assert result["ok"] is False
    assert "Unsupported video type" in result["error"]
