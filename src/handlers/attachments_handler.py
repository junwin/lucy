"""Find images from earlier turns without uploading their bytes again."""

from src.attachments import ConversationAttachments, export_conversation_images
from src.handlers.handler_v2 import HandlerV2


class AttachmentsHandler(HandlerV2):
    NAME = "attachments"

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
                "Find uploaded or generated images from earlier turns in the current chat. "
                "List returns newest turns first, with filenames and image IDs, even beyond "
                "recent prompt history. Get checks one image ID belongs to this chat. "
                "Reuse image_id with video_generate or image_generate.image_ids. "
                "last_video_id identifies a video made from that still, for prompt revisions; use the storage path "
                "with serve_image to show a candidate. Never invent an ID or request another "
                "upload before checking here. If several images match, ask which one to use. Export copies images to a fresh batch under an approved external_root and relative_path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["list", "get", "export"]},
                    "image_id": {"type": "string", "description": "ID for get; empty string for list."},
                    "offset": {"type": "integer", "minimum": 0, "description": "List offset; 0 for get."},
                    "count": {"type": "integer", "minimum": 1, "maximum": 20,
                              "description": "List page size; 1 for get."},
                    "image_ids": {"type": ["array", "null"], "items": {"type": "string"},
                                  "description": "Export: IDs from current conversation."},
                    "external_root": {"type": ["string", "null"],
                                      "description": "Export: approved external root name, e.g. pictures."},
                    "relative_path": {"type": ["string", "null"],
                                      "description": "Export: directory relative to the root, e.g. incomming-mp."},
                    "collision": {"type": ["string", "null"], "enum": ["rename", "fail", None]},
                },
                "required": ["action", "image_id", "offset", "count", "image_ids", "external_root", "relative_path", "collision"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls):
        return {"type": "object", "properties": {
            "ok": {"type": "boolean"}, "tool": {"type": "string"},
            "images": {"type": "array", "items": {"type": "object"}},
            "total": {"type": "integer"}, "next_offset": {"type": ["integer", "null"]},
            "error": {"type": "string"},
            "exported": {"type": "array", "items": {"type": "object"}},
            "count": {"type": "integer"}, "batch_directory": {"type": "string"},
            "external_root": {"type": "string"}, "relative_path": {"type": "string"},
            "batch_relative_path": {"type": "string"},
        }, "required": ["ok", "tool"], "additionalProperties": False}

    def execute(self, args, *, account_name="auto", **context):
        try:
            session_id = context.get("conversation_id")
            if not session_id or not account_name or account_name == "auto":
                raise ValueError("Current account and conversation are required")
            action = args.get("action")
            if action not in {"list", "get", "export"}:
                raise ValueError("action must be list, get or export")
            count, offset = args.get("count", 10), args.get("offset", 0)
            if type(count) is not int or not 1 <= count <= 20:
                raise ValueError("count must be between 1 and 20")
            if type(offset) is not int or offset < 0:
                raise ValueError("offset must be a nonnegative integer")
            if action == "export":
                result = export_conversation_images(
                    self.config, context.get("episodic_store"),
                    account_name=account_name, session_id=session_id,
                    image_ids=args.get("image_ids"),
                    external_root=args.get("external_root"),
                    relative_path=args.get("relative_path"),
                    collision=args.get("collision") or "rename",
                )
                return {"ok": True, "tool": self.NAME, **result}
            images = ConversationAttachments(self.config, context.get("episodic_store")).images(
                account_name=account_name, session_id=session_id,
            )
            if action == "get":
                selected = [image for image in images if image["image_id"] == args.get("image_id")]
                if not selected:
                    raise ValueError("Image not found in this conversation, or its file is unavailable")
                return {"ok": True, "tool": self.NAME, "images": selected}
            selected = images[offset:offset + count]
            next_offset = offset + count if offset + count < len(images) else None
            return {"ok": True, "tool": self.NAME, "images": selected,
                    "total": len(images), "next_offset": next_offset}
        except (ValueError, OSError) as exc:
            return {"ok": False, "tool": self.NAME, "error": str(exc)}
