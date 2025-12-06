import logging
import json
from typing import List

import requests

from src.handlers.handler import Handler
from src.container_config import container
from src.config_manager import ConfigManager

# Brave Search API endpoint
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

config = container.get(ConfigManager)
credential_path = config.get("credential_path")

# Expect a brave.json file with { "subscription_key": "..." }
with open(credential_path + "/brave.json", "r") as config_file:
    config_data = json.load(config_file)

BRAVE_SUBSCRIPTION_KEY = config_data["subscription_key"]



class WebSearchHandler(Handler):  # Concrete handler

    functDef = {
        "name": "web_search_handler",
        "description": "use Brave Search to search the web",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "the string used to query the web",
                },
            },
            "required": ["query"],
        },
    }

    def get_function_calling_definition(self):
        return self.functDef

    def handle(self, action: dict, account_name: str = "auto") -> List[dict]:
        action_name = action["action_name"]
        if action_name not in ["action_web_search", "web_search_handler"]:
            return None

        logging.info(self.__class__.__name__)

        query = action["query"]
        result_type = "webpages"
        if "result_type" in action:
            result_type = action["result_type"]

        result = self.brave_search(query, result_type)

        temp = [{"result": result}, {"handler": self.__class__.__name__}]
        temp.append(action)
        return temp

    def brave_search(self, query: str, result_type: str) -> List[dict]:
        """Call Brave Search API and normalize results.

        Currently we only support web results, returned as a list of
        {"url", "name", "description"} dicts, similar to the previous
        Bing-based implementation.
        """
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": BRAVE_SUBSCRIPTION_KEY,
            }
            params = {
                "q": query,
                "count": 10,  # default number of results
            }

            response = requests.get(BRAVE_ENDPOINT, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = self.get_results(data, result_type)
            return result

        except Exception as e:
            logging.exception("Error occurred while calling Brave Search API")
            return [{"error": str(e)}]

    def get_results(self, data, result_type: str) -> List[dict]:
        """Extract web results from Brave response in a Bing-like shape."""
        results: List[dict] = []

        # Brave's web results live under data["web"]["results"]
        web_block = data.get("web", {})
        items = web_block.get("results", [])

        for item in items:
            results.append(
                {
                    "url": item.get("url"),
                    "name": item.get("title"),
                    "description": item.get("description"),
                }
            )

        return results
