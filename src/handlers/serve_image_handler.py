"""Serve existing images through the same delivery service as generated images."""
from pathlib import Path
from typing import Any, Dict
from src.handlers.handler_v2 import HandlerV2
from src.image_presentation import ImagePresentationService, DEFAULT_MAX_DIMENSION


class ServeImageHandler(HandlerV2):
    NAME = "serve_image"

    def __init__(self, config):
        self.config = config
        self.presentation = ImagePresentationService(config)

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
                "image file, you MUST call this tool immediately. Do not ask clarifying "
                "questions about where or how to display it. Resolves an image file from "
                "disk and returns a compact reference. Lucy delivers its bytes separately."
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
                            f"Default is {DEFAULT_MAX_DIMENSION} (hard cap)."
                        ),
                    },
                },
                "required": ["location", "external_root", "path", "max_dimension"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls):
        return {"type": "object", "properties": {
            "ok": {"type": "boolean"}, "tool": {"type": "string"},
            "error": {"type": "string"}, "image": {"type": "object"},
        }, "required": ["ok"], "additionalProperties": False}

    def execute(self, args, *, account_name="auto", **context):
        reference = {
            "location": (args.get("location") or "storage").strip().lower(),
            "external_root": (args.get("external_root") or "").strip(),
            "path": (args.get("path") or "").strip(),
            "max_dimension": args.get("max_dimension", DEFAULT_MAX_DIMENSION),
        }
        try:
            max_dim = reference["max_dimension"]
            if not isinstance(max_dim, int) or isinstance(max_dim, bool) or max_dim <= 0:
                raise ValueError("max_dimension must be a positive integer")
            reference["max_dimension"] = min(max_dim, DEFAULT_MAX_DIMENSION)
            self.presentation.resolve(reference, account_name)
            parts = [part for part in reference["path"].replace("\\", "/").split("/")
                     if part not in ("", ".")]
            if reference["location"] == "storage" and len(parts) == 3 and parts[0] == "images":
                # Use the same identity as automatic generation delivery.
                reference["image_id"] = Path(parts[2]).stem
            reference["alt"] = Path(reference["path"]).name
            return {"ok": True, "tool": self.NAME, "image": reference}
        except (ValueError, OSError) as exc:
            return {"ok": False, "tool": self.NAME, "error": str(exc)}
