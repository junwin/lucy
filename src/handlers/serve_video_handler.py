"""Display an existing generated MP4 through Lucy's video event delivery path."""

from typing import Any, Dict
from urllib.parse import quote
from src.handlers.handler_v2 import HandlerV2
from src.http_endpoints.upload_endpoints import get_video_download_impl


class ServeVideoHandler(HandlerV2):
    """Return a compact browser-delivery reference for an account-owned video."""

    NAME = "serve_video"

    def __init__(self, config):
        self.config = config

    @classmethod
    def name(cls):
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "REQUIRED — when the user asks to see, show, or display a specific "
                "video that Lucy generated, call this tool immediately. Do not ask "
                "where or how to display it. Supply its video_id; Lucy sends the MP4 "
                "to the browser using the same video event as video generation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "UUID of an existing generated video.",
                    },
                },
                "required": ["video_id"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls):
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "error": {"type": "string"},
                "video": {"type": "object"},
            },
            "required": ["ok"],
            "additionalProperties": False,
        }

    def execute(self, args, *, account_name="auto", **context):
        video_id = (args.get("video_id") or "").strip()
        if not video_id:
            return {"ok": False, "tool": self.NAME, "error": "video_id is required"}

        path, metadata, status = get_video_download_impl(
            self.config, account_name, video_id
        )
        if status != 200 or path is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": metadata.get("error", "Video is unavailable"),
            }

        normalized_id = metadata["id"]
        return {
            "ok": True,
            "tool": self.NAME,
            "video": {
                "url": (
                    f"/download/video/{normalized_id}"
                    f"?accountName={quote(account_name, safe='')}"
                ),
                "mime_type": "video/mp4",
                "download_name": f"{normalized_id}.mp4",
                "video_id": normalized_id,
            },
        }
