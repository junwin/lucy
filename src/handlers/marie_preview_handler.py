"""Gwen's Marie-Parie preview session operations, independent of HTTP transport."""
from src.handlers.handler_v2 import HandlerV2
from src.marie_preview import MariePreviewService


class MariePreviewHandler(HandlerV2):
    NAME = "marie_preview"

    def __init__(self, config):
        self.config = config

    @classmethod
    def name(cls):
        return cls.NAME

    @classmethod
    def tool_def(cls):
        return {
            "type": "function", "name": cls.NAME,
            "description": (
                "Manage a private Marie-Parie website editing session. "
                "Create a Git worktree from remote staging, review its temporary preview, "
                "save a gallery order, share the preview branch for debugging, "
                "publish approved changes to staging, or cancel. "
                "Never publish or cancel without explicit user confirmation. "
                "The preview's worktree path can be supplied as --repo to marie-publish "
                "when preparing the initial images, without --commit or --push. "
                "view_path and editor_path belong to Lucy's Flask server, NOT "
                "Cloudflare staging. For local Mint tests use http://localhost:5000 "
                "as the base URL; for remote use the actual Lucy ngrok origin. "
                "Never guess a staging hostname for a temporary preview."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "list", "status", "gallery", "save_gallery", "share", "publish", "cancel"]},
                    "session_id": {"type": ["string", "null"]},
                    "collection": {"type": ["string", "null"]},
                    "images": {"type": ["array", "null"], "items": {"type": "string"}},
                    "expected_sha": {"type": ["string", "null"]},
                },
                "required": ["action", "session_id", "collection", "images", "expected_sha"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls):
        return {"type": "object", "properties": {
            "ok": {"type": "boolean"},
            "tool": {"type": "string"},
            "action": {"type": "string"},
            "data": {"type": ["object", "null"]},
            "error": {"type": ["string", "null"]},
        }, "required": ["ok", "tool", "action", "data", "error"], "additionalProperties": False}

    def execute(self, args, *, account_name="auto", **context):
        action = args.get("action")
        try:
            if not account_name or account_name == "auto":
                raise ValueError("An authenticated account is required")
            service = MariePreviewService(self.config)
            sid = args.get("session_id")
            if action == "create":
                data = service.create(account_name)
            elif action == "list":
                data = service.list(account_name)
            elif action == "status":
                data = service.status(sid, account_name)
            elif action == "gallery":
                data = service.gallery(sid, account_name, args.get("collection"))
            elif action == "save_gallery":
                data = service.save_gallery(sid, account_name, args.get("collection"),
                                            args.get("images"), args.get("expected_sha"))
            elif action == "share":
                data = service.share(sid, account_name)
            elif action == "publish":
                data = service.publish(sid, account_name)
            elif action == "cancel":
                data = service.cancel(sid, account_name)
            else:
                raise ValueError("Unknown Marie-Parie preview action")
            return {"ok": True, "tool": self.NAME, "action": action, "data": data, "error": None}
        except (ValueError, OSError, __import__("subprocess").CalledProcessError) as error:
            return {"ok": False, "tool": self.NAME, "action": action, "data": None,
                    "error": str(error)}
