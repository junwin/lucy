"""Display MP4 files through Lucy's existing video event delivery path."""

from typing import Any, Dict

from src.handlers.handler_v2 import HandlerV2
from src.video_presentation import VideoPresentationService


class ServeVideoHandler(HandlerV2):
    """Return a compact browser-delivery reference for an MP4."""

    NAME = "serve_video"

    def __init__(self, config):
        self.config = config
        self.presentation = VideoPresentationService(config)

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
                "video file, call this tool immediately. Do not ask where or how to "
                "display it. For a generated video, supply its video_id. For a file, "
                "supply location and path (and external_root when needed). Lucy sends "
                "the MP4 to the browser using the same video event as generation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {
                        "type": "string",
                        "description": "UUID of an existing generated video; use '' for a file path.",
                    },
                    "location": {
                        "type": "string",
                        "enum": ["storage", "external"],
                        "description": "Where to load the file from; use 'storage' for a generated video_id.",
                    },
                    "external_root": {
                        "type": "string",
                        "description": "Named external root key when location='external'. Use '' otherwise.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Relative path to an MP4 under the chosen location; use '' for a generated video_id.",
                    },
                },
                "required": ["video_id", "location", "external_root", "path"],
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
        reference = {
            "video_id": (args.get("video_id") or "").strip(),
            "location": (args.get("location") or "storage").strip().lower(),
            "external_root": (args.get("external_root") or "").strip(),
            "path": (args.get("path") or "").strip(),
        }
        try:
            _path, mime_type, video = self.presentation.resolve(reference, account_name)
            return {
                "ok": True,
                "tool": self.NAME,
                "video": {
                    "url": video["url"],
                    "mime_type": mime_type,
                    "download_name": video["download_name"],
                    "video_id": video["video_id"],
                },
            }
        except (ValueError, OSError) as exc:
            return {"ok": False, "tool": self.NAME, "error": str(exc)}
