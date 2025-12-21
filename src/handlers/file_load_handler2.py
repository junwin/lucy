# /home/junwin/src/repos/lucy/src/handlers/file_load_handler2.py

import os
import json
import logging
from typing import Any, Dict, Tuple, Union, List

from src.config_manager import ConfigManager
from src.chunkers.chuncked_file_processor import ChunkedFileProcessor
from src.chunkers.text_chunker import TextChunker
from src.handlers.handler_utils import get_base_path
from src.handlers.handler_v2 import HandlerV2


class FileLoadHandler2(HandlerV2):
    NAME = "file_load"

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
                "description": "Load a file from a directory relative to the allowed base folder and chunk if needed",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory_path": {
                            "type": "string",
                            "description": "Location of the file relative to the allowed base folder",
                        },
                        "file_name": {
                            "type": "string",
                            "description": "Name of the file to be loaded",
                        },
                    },
                    "required": ["directory_path", "file_name"],
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
                "file_name": {"type": "string"},
                "directory_path": {"type": "string"},
                "resolved_path": {"type": "string"},
                "chunked": {"type": "boolean"},
                "content_type": {"type": "string"},
                "encoding": {"type": "string"},
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
        directory_path = (args.get("directory_path") or "").strip()
        file_name = (args.get("file_name") or "").strip()

        if not directory_path or not file_name:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "directory_path and file_name are required",
                "args": {"directory_path": directory_path, "file_name": file_name},
            }

        # Resolve to allowed base path
        base_path = get_base_path(self.config, account_name, directory_path)

        try:
            content, full_path = self._read_file_safe(base_path, file_name)
        except Exception as e:
            logging.exception("file_load failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "directory_path": directory_path,
                "file_name": file_name,
                "base_path": base_path,
            }

        file_chunk_threshold = int(self.config.get("file_chunk_threshold"))
        file_chunk_size = int(self.config.get("file_chunk_size"))

        chunked = False
        result: Union[str, Dict[str, Any]] = content

        if content is not None and len(content) > file_chunk_threshold:
            chunk_processor = ChunkedFileProcessor()
            chunker = TextChunker()

            chunked_content = chunk_processor.process_text_data(content, chunker, file_chunk_size)
            chunked = True

            chunks: List[str]
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
            "file_name": file_name,
            "directory_path": directory_path,
            "resolved_path": full_path,
            "chunked": chunked,
            "content_type": "text/plain",
            "encoding": "utf-8",
            "result": result,
        }

    def execute_as_tool_content(self, args: Dict[str, Any], *, account_name: str = "auto") -> str:
        return json.dumps(self.execute(args, account_name=account_name), ensure_ascii=False)

    def _read_file_safe(self, base_path: str, file_name: str) -> Tuple[str, str]:
        base_abs = os.path.abspath(base_path)

        if os.path.sep in file_name or (os.path.altsep and os.path.altsep in file_name):
            raise ValueError("file_name must not contain path separators")

        full_path = os.path.abspath(os.path.join(base_abs, file_name))

        if not (full_path == base_abs or full_path.startswith(base_abs + os.path.sep)):
            raise ValueError("File access outside allowed base path")

        with open(full_path, "r", encoding="utf-8") as f:
            return f.read(), full_path
