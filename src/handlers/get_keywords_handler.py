from __future__ import annotations

from typing import Any, Dict

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.keywords.keywords import Keywords


class GetKeywordsHandler(HandlerV2):
    """Handler that exposes keyword extraction as a tool.

    This follows the HandlerV2 contract: name(), tool_def(), result_schema(), execute().
    The handler deliberately does not attempt to download NLTK/spaCy data; the
    Keywords class is responsible for loading models and will raise helpful errors
    if required resources are missing.
    """

    # Tool name (use short, consistent tool naming like other handlers)
    NAME = "get_keywords"

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Extract keywords from a string",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Text to extract keywords from",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Maximum number of keywords to return",
                        "default": 10,
                    },
                    "language_code": {
                        "type": "string",
                        "description": "Language code for keyword extraction (e.g. 'en', 'es')",
                        "default": "en",
                    },
                },
                # strict=True => required must include every key in properties
                "required": ["content", "top_n", "language_code"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], **context: Any) -> Dict[str, Any]:
        content = (args.get("content") or "").strip()
        top_n = args.get("top_n", 10)
        language_code = (args.get("language_code") or "en").strip() or "en"

        if not content:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "content is required",
            }

        if not isinstance(top_n, int) or top_n <= 0:
            top_n = 10

        try:
            kw = Keywords(language_code=language_code)
            keywords = kw.extract_keywords(content, top_n=top_n)
            return {
                "ok": True,
                "tool": self.NAME,
                "keywords": keywords,
            }
        except Exception as e:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
            }
