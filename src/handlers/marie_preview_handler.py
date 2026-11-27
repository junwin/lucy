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
                "save a gallery order, import a selected prepared website image batch, "
                "share the preview branch for debugging, "
                "publish approved changes to staging, or cancel. "
                "Never publish or cancel without explicit user confirmation. "
                "For new images in the normal Gwen flow, use import_batch instead "
                "of marie-publish; the import operation transfers actual JPEG bytes. "
                "For new or repeated uploads ALWAYS use import_batch with the current "
                "batch_id after approved filenames, before claiming preview updates. "
                "save_gallery ONLY changes the display list; it NEVER copies photos. "
                "import_batch copies the new batch and safely disambiguates same-name "
                "different-content photos; replace=true substitutes the gallery list. "
                "The response contains complete view_url and editor_url fields "
                "built by Lucy. Link ONLY those exact URLs from the tool result. "
                "Never reconstruct links from view_path, use Cloudflare staging "
                "for temporary previews, or reuse an old URL without checking status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "list", "status", "gallery", "save_gallery", "import_batch", "share", "publish", "cancel"]},
                    "session_id": {"type": ["string", "null"]},
                    "collection": {"type": ["string", "null"]},
                    "images": {"type": ["array", "null"], "items": {"type": "string"}},
                    "expected_sha": {"type": ["string", "null"]},
                    "batch_id": {"type": ["string", "null"], "description": "For import_batch: exact ID of the current prepared web image batch"},
                    "replace": {"type": ["boolean", "null"], "description": "For import_batch: replace gallery display list rather than append; never deletes originals"},
                },
                "required": ["action", "session_id", "collection", "images", "expected_sha", "batch_id", "replace"],
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
            elif action == "import_batch":
                data = service.import_web_batch(sid, account_name, args.get("collection"),
                                                args.get("batch_id"),
                                                replace=args.get("replace"),
                                                expected_sha=args.get("expected_sha"))
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
