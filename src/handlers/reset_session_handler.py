"""ResetSessionHandler — clears the current session's events and signals the client.

This handler truncates the session's events file on the server (via chat2_store)
and returns {"action": "reset_session"} to signal the streaming SSE loop that
the client should also refresh/clear its local view.
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
                "ok": {"type": "boolean"},
            },
            "required": ["action"],
            "additionalProperties": False,
        }

    def execute(
        self, args: Dict[str, Any], *, account_name: str = "auto", **context
    ) -> Dict[str, Any]:
        conversation_id = context.get("conversation_id", "")
        chat2_store = context.get("chat2_store")

        logger.info("Reset session triggered for session=%s (account=%s)", conversation_id, account_name)

        if not conversation_id:
            logger.warning("Reset session: no conversation_id in context")
            return {"action": "reset_session", "ok": False, "error": "No session ID available"}

        try:
            if chat2_store is not None:
                chat2_store.reset_events(conversation_id)
                logger.info("Reset session: cleared events for session=%s", conversation_id)
            else:
                logger.warning("Reset session: no chat2_store available for session=%s", conversation_id)
                return {"action": "reset_session", "ok": False, "error": "chat2_store not available"}
        except ValueError as e:
            logger.warning("Reset session: session not found: %s", conversation_id)
            return {"action": "reset_session", "ok": False, "error": str(e)}
        except Exception as e:
            logger.exception("Reset session: failed to clear events for session=%s", conversation_id)
            return {"action": "reset_session", "ok": False, "error": str(e)}

        return {"action": "reset_session", "ok": True}

    def execute_raw(
        self, arguments_raw: str, *, account_name: str = "auto", call_id: str = "", **context
    ) -> str:
        result = self.execute({}, account_name=account_name, **context)
        return json.dumps(result, ensure_ascii=False)
