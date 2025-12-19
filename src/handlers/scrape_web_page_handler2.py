import json
import logging
from typing import Any, Dict

from src.config_manager import ConfigManager
from src.chunkers.chuncked_file_processor import ChunkedFileProcessor
from src.chunkers.text_chunker import TextChunker
from src.handlers.handler_utils import get_base_path, execute_script
from src.handlers.handler_v2 import HandlerV2


class ScrapeWebPageHandler2(HandlerV2):
    NAME = "scrape_web_page"

    def __init__(self, config: ConfigManager):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cls.NAME,
                "description": "Read the text from a webpage and chunk if needed",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_url": {
                            "type": "string",
                            "description": "The URL of the page to be scraped",
                        },
                    },
                    "required": ["page_url"],
                    "additionalProperties": False,
                },
            },
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "page_url": {"type": "string"},
                "chunked": {"type": "boolean"},
                "result": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "chunks": {"type": "array", "items": {"type": "string"}},
                                "chunk_count": {"type": "integer"},
                                "chunk_size": {"type": "integer"},
                            },
                            "required": ["chunks", "chunk_count", "chunk_size"],
                            "additionalProperties": False,
                        },
                    ]
                },
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        page_url = (args.get("page_url") or "").strip()

        if not page_url:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "page_url is required",
                "args": {"page_url": page_url},
            }

        logging.info(self.__class__.__name__)

        python_utils_path = self.config.get("python_utils_path")
        base_path = get_base_path(self.config, account_name, python_utils_path)

        command = f"python3 scrape.py {page_url}"

        try:
            result_text = execute_script(command, base_path)
        except Exception as e:
            logging.exception("scrape_web_page failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "page_url": page_url,
                "python_utils_path": python_utils_path,
                "base_path": base_path,
            }

        file_chunk_threshold = int(self.config.get("file_chunk_threshold"))
        file_chunk_size = int(self.config.get("file_chunk_size"))

        chunked = False
        result: Any = result_text

        if result_text is not None and len(result_text) > file_chunk_threshold:
            chunk_processor = ChunkedFileProcessor()
            chunker = TextChunker()

            chunked_content = chunk_processor.process_text_data(result_text, chunker, file_chunk_size)
            chunked = True

            if isinstance(chunked_content, list):
                chunks = [str(x) for x in chunked_content]
            elif isinstance(chunked_content, dict) and "chunks" in chunked_content:
                chunks = [str(x) for x in (chunked_content.get("chunks") or [])]
            else:
                chunks = [str(chunked_content)]

            result = {"chunks": chunks, "chunk_count": len(chunks), "chunk_size": file_chunk_size}

        return {
            "ok": True,
            "tool": self.NAME,
            "page_url": page_url,
            "chunked": chunked,
            "result": result,
        }

    def execute_as_tool_content(self, args: Dict[str, Any], *, account_name: str = "auto") -> str:
        return json.dumps(self.execute(args, account_name=account_name), ensure_ascii=False)
