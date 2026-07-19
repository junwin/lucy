"""ResetSessionHandler — SSE Phase 2 action: triggers a session reset.

This handler returns {"action": "reset_session"} to signal the streaming
SSE loop that the client should refresh/clear its session. It has no required
parameters.
"""

import json
import logging
from typing import Any, Dict

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2

logger = logging.getLogger(__name__)


class ResetSessionHandler(HandlerV2):
    NAME = "reset_session"

    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Reset the current chat session. Use this when the user asks to start fresh, clear history, or begin a new session.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "strict": True,
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
            },
            "required": ["action"],
            "additionalProperties": False,
        }

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        logger.info("Reset session action triggered (account=%s)", account_name)
        return {"action": "reset_session"}

    def execute_raw(
        self, arguments_raw: str, *, account_name: str = "auto", call_id: str = ""
    ) -> str:
        result = self.execute({}, account_name=account_name)
        return json.dumps(result, ensure_ascii=False)
