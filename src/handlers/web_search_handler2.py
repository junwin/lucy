import json
import logging
from typing import Any, Dict, List

import requests

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2

# Brave Search API endpoint
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class WebSearchHandler2(HandlerV2):
    NAME = "web_search_handler"

    def __init__(self, config: ConfigManager | None = None):
        # Allow explicit injection for tests, otherwise use container
        self.config = config or container.get(ConfigManager)

        credential_path = self.config.get("credential_path")
        with open(f"{credential_path}/brave.json", "r", encoding="utf-8") as config_file:
            config_data = json.load(config_file)

        self.subscription_key = config_data["subscription_key"]

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": cls.NAME,
                "description": "Use Brave Search to search the web",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The string used to query the web",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default 10)",
                        },
                    },
                    "required": ["query"],
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
                "query": {"type": "string"},
                "result_type": {"type": "string"},
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "required": ["url", "name"],
                        "additionalProperties": True,
                    },
                },
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto") -> Dict[str, Any]:
        query = (args.get("query") or "").strip()
        count = args.get("count")

        if not query:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "query is required",
                "args": {"query": query},
            }

        if not isinstance(count, int) or count <= 0:
            count = 10

        try:
            results = self._brave_search(query=query, count=count)
            return {
                "ok": True,
                "tool": self.NAME,
                "query": query,
                "result_type": "webpages",
                "results": results,
            }
        except Exception as e:
            logging.exception("web_search_handler failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": str(e),
                "query": query,
            }

    def execute_as_tool_content(self, args: Dict[str, Any], *, account_name: str = "auto") -> str:
        return json.dumps(self.execute(args, account_name=account_name), ensure_ascii=False)

    def _brave_search(self, *, query: str, count: int) -> List[Dict[str, Any]]:
        """Call Brave Search API and normalize results.

        Returns a list of {"url", "name", "description"} dicts.
        """
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.subscription_key,
        }
        params = {
            "q": query,
            "count": count,
        }

        response = requests.get(BRAVE_ENDPOINT, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return self._extract_results(data)

    def _extract_results(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        web_block = data.get("web", {}) or {}
        items = web_block.get("results", []) or []

        for item in items:
            results.append(
                {
                    "url": item.get("url", ""),
                    "name": item.get("title", ""),
                    "description": item.get("description", ""),
                }
            )

        return results
