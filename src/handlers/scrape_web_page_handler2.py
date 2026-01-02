import json
import logging
from typing import Any, Dict

from src.config_manager import ConfigManager
from src.handlers.handler_utils import get_base_path, execute_script
from src.handlers.handler_v2 import HandlerV2

# Define a module-level logger
logger = logging.getLogger(__name__)

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
            "name": cls.NAME,
            "description": "Read the text from a webpage",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_url": {
                        "type": "string",
                        "description": "The URL of the page to be scraped",
                    },
                },
                # STRICT MODE: ALL PROPERTIES MUST BE REQUIRED
                "required": [
                    "page_url",
                ],
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
                "page_url": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        page_url = (args.get("page_url") or "").strip()

        if not page_url:
            logger.warning("page_url is required")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "page_url is required",
                "args": {"page_url": page_url},
            }

        logger.info("Executing scrape for page_url: %s", page_url)

        python_utils_path = self.config.get("python_utils_path")
        base_path = get_base_path(self.config, account_name, python_utils_path)

        command = f"python3 scrape.py {page_url}"

        try:
            logger.debug("Executing command: %s", command)
            result_text = execute_script(command, base_path)
            logger.info("Scraping completed successfully for page_url: %s", page_url)
        except Exception as e:
            logger.exception("scrape_web_page failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "page_url": page_url,
                "python_utils_path": python_utils_path,                "name": cls.name(),
                "base_path": base_path,
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "page_url": page_url,
            "result": result_text,
        }

    def execute_as_tool_content(self, args: Dict[str, Any], *, account_name: str = "auto") -> str:
        return json.dumps(self.execute(args, account_name=account_name), ensure_ascii=False)
