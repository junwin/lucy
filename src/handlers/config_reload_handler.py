"""Tool handler for runtime reload of configuration and agents.

Tool name: config_reload

This wraps the same validate-then-publish routine that backs
``POST /admin/reload`` (``src.http_endpoints.admin_reload``), so the model can
refresh ``config.json`` / ``config.local.json`` and the agents file without an
HTTP round trip and without holding the API key.

The handler uses the live ``ConfigManager`` and ``AgentManager`` passed in the
handler execution context (keys ``config`` and ``agent_manager``). Both must be
the shared instances the application uses: reloading a copy would report
success while the running server kept its old state. When the manager is not
available the handler fails instead of silently building a throwaway instance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from src.handlers.handler_v2 import HandlerV2
from src.http_endpoints.admin_reload import reload_config_and_agents

logger = logging.getLogger(__name__)

# Methods the reload routine requires on the config object. Checking them here
# produces a clear tool error when a plain dict is passed instead of the live
# ConfigManager.
_CONFIG_METHODS = ("read_reload_config", "apply_config")


class ConfigReloadHandler(HandlerV2):
    NAME = "config_reload"

    def __init__(self, config: Any):
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Reload runtime configuration and agent definitions from disk. "
                "Both the merged config (config.json plus optional "
                "config.local.json) and every agent in the configured agents "
                "file are validated first; nothing is published unless both "
                "pass. Startup-created services (stores, provider clients, "
                "host/port) are not rebuilt — restart for those."
            ),
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
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "config_reloaded": {"type": "boolean"},
                "keys_added": {"type": "array", "items": {"type": "string"}},
                "keys_removed": {"type": "array", "items": {"type": "string"}},
                "keys_changed": {"type": "array", "items": {"type": "string"}},
                "agents_loaded": {"type": "integer"},
                "agent_names": {"type": "array", "items": {"type": "string"}},
                "agents_added": {"type": "array", "items": {"type": "string"}},
                "agents_removed": {"type": "array", "items": {"type": "string"}},
                "failed_stage": {"type": "string"},
                "error": {"type": ["object", "null"]},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def _fail(self, code: str, message: str) -> Dict[str, Any]:
        logger.warning("config_reload rejected: %s (%s)", code, message)
        return {
            "ok": False,
            "tool": self.NAME,
            "config_reloaded": False,
            "error": {"code": code, "message": message},
        }

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:
        logger.info("config_reload input account=%s", account_name)

        config = context.get("config")
        if config is None:
            config = self.config
        agent_manager = context.get("agent_manager")

        if agent_manager is None:
            return self._fail(
                "missing_agent_manager",
                "config_reload needs the shared agent_manager in the handler "
                "context; a reload on a private instance would not affect the "
                "running application.",
            )

        missing = [name for name in _CONFIG_METHODS if not callable(getattr(config, name, None))]
        if missing:
            return self._fail(
                "config_manager_required",
                "config_reload needs the live ConfigManager (missing "
                f"{', '.join(missing)}); got {type(config).__name__}.",
            )

        body, status = reload_config_and_agents(config, agent_manager)

        if status != 200:
            return {
                "ok": False,
                "tool": self.NAME,
                "config_reloaded": False,
                "failed_stage": body.get("failed_stage", ""),
                "error": {
                    "code": "reload_failed",
                    "message": body.get("error", "Reload failed."),
                    "detail": body.get("detail", ""),
                },
            }

        return {"ok": True, "tool": self.NAME, **body}


__all__ = ["ConfigReloadHandler"]
