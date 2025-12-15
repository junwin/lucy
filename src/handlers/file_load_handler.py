import os
import re
import json
import logging
from typing import Any, Dict, Optional, Tuple, Union, List

from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager
from src.chunkers.chuncked_file_processor import ChunkedFileProcessor
from src.chunkers.text_chunker import TextChunker
from src.handlers.handler_utils import get_base_path


class FileLoadHandler(Handler):
    """
    Tool: file_load
    Loads a file from a directory relative to an allowed base path.
    If large, chunks the content.
    Returns a STRING (JSON) suitable to send back as a tool result.
    """

    functDef = {
        "name": "file_load",
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
    }

    def get_function_calling_definition(self) -> Dict[str, Any]:
        return self.functDef

    def handle(self, action: Dict[str, Any], account_name: str = "auto") -> Optional[str]:
        """
        Returns:
          - None if action isn't for us
          - otherwise a JSON string with result + metadata
        """
        action_name = action.get("action_name")
        if action_name != "file_load":
            return None

        logging.info("%s handling file_load", self.__class__.__name__)

        directory_path = (action.get("directory_path") or "").strip()
        file_name = (action.get("file_name") or "").strip()

        if not directory_path or not file_name:
            return json.dumps(
                {
                    "ok": False,
                    "error": "directory_path and file_name are required",
                    "handler": self.__class__.__name__,
                    "action": action,
                },
                ensure_ascii=False,
            )

        config = container.get(ConfigManager)

        # Resolve to an allowed base path (your existing sandbox logic)
        base_path = get_base_path(config, account_name, directory_path)

        # Read file with traversal protection
        try:
            content, full_path = self._read_file_safe(base_path, file_name)
        except Exception as e:
            logging.exception("file_load failed")
            return json.dumps(
                {
                    "ok": False,
                    "error": str(e),
                    "handler": self.__class__.__name__,
                    "directory_path": directory_path,
                    "file_name": file_name,
                    "base_path": base_path,
                },
                ensure_ascii=False,
            )

        file_chunk_threshold = int(config.get("file_chunk_threshold"))
        file_chunk_size = int(config.get("file_chunk_size"))

        chunked = False
        result: Union[str, Dict[str, Any]] = content

        if content is not None and len(content) > file_chunk_threshold:
            chunk_processor = ChunkedFileProcessor()
            chunker = TextChunker()

            chunked_content = chunk_processor.process_text_data(content, chunker, file_chunk_size)
            chunked = True

            # Make a stable schema for chunked results.
            # We don’t assume the exact type returned by ChunkedFileProcessor; normalize it.
            chunks: List[str]
            if isinstance(chunked_content, list):
                chunks = [str(x) for x in chunked_content]
            elif isinstance(chunked_content, dict) and "chunks" in chunked_content:
                chunks = [str(x) for x in (chunked_content.get("chunks") or [])]
            else:
                # Fallback: store as a single “chunk” string
                chunks = [str(chunked_content)]

            result = {
                "chunks": chunks,
                "chunk_count": len(chunks),
                "chunk_size": file_chunk_size,
            }

        payload = {
            "ok": True,
            "handler": self.__class__.__name__,
            "tool": "file_load",
            "file_name": file_name,
            "directory_path": directory_path,
            "resolved_path": full_path,
            "chunked": chunked,
            "content_type": "text/plain",
            "encoding": "utf-8",
            "result": result,
        }

        # IMPORTANT: tool message content must be a string
        return json.dumps(payload, ensure_ascii=False)

    def process_inline_file(self, message: str) -> str:
        """
        Legacy helper: replaces occurrences of file_path:<path> with file contents.
        NOTE: This bypasses tool calling. Use carefully.
        """
        file_paths = re.findall(r"file_path:(\S+)", message)

        for file_path in file_paths:
            directory, filename = os.path.split(file_path)
            try:
                with open(os.path.join(directory, filename), "r", encoding="utf-8") as f:
                    file_contents = f.read()
                message = message.replace(f"file_path:{file_path}", file_contents, 1)
            except Exception as e:
                logging.warning("process_inline_file failed for %s: %s", file_path, e)

        return message

    def _read_file_safe(self, base_path: str, file_name: str) -> Tuple[str, str]:
        """
        Reads file_name inside base_path safely.
        Prevents path traversal via file_name like ../../etc/passwd
        """
        base_abs = os.path.abspath(base_path)

        # Force file_name to be a file name, not a path. If you WANT subfolders, remove this.
        if os.path.sep in file_name or (os.path.altsep and os.path.altsep in file_name):
            raise ValueError("file_name must not contain path separators")

        full_path = os.path.abspath(os.path.join(base_abs, file_name))

        # Ensure full path is within base path
        if not (full_path == base_abs or full_path.startswith(base_abs + os.path.sep)):
            raise ValueError("File access outside allowed base path")

        with open(full_path, "r", encoding="utf-8") as f:
            return f.read(), full_path
