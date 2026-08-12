"""Tool handler for managing agent definitions at runtime.

Tool name: agents_manage

Actions:
  - list     -> return all agent names
  - get      -> return a single agent definition (by name)
  - upsert   -> create or update an agent, then persist to disk
  - delete   -> remove an agent by name, then persist to disk
  - reload   -> re-read agents from the configured agents file

The handler prefers the *shared* AgentManager instance passed in the handler
execution context (key "agent_manager"). This is the same singleton the rest of
the application uses, so upsert/reload/delete affect the live agent list.

If no shared instance is present (e.g. direct construction in tests), a
standalone AgentManager is built from config. This is functional but a reload
on that standalone instance will not refresh the live app's agent list — the
handler logs a warning to make that limitation explicit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.agent import Agent
from src.agent.agent_manager import AgentManager
from src.handlers.handler_v2 import HandlerV2

logger = logging.getLogger(__name__)


class AgentsManageHandler(HandlerV2):
    NAME = "agents_manage"

    def __init__(self, config: Any):
        # keep signature compatible with registry.create(name, config=...)
        self.config = config

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Manage agent definitions: list, get, upsert (create/update), delete, or reload from disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "get", "upsert", "delete", "reload"],
                        "description": "Operation to perform.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Agent name. Required for get, delete.",
                    },
                    "agent": {
                        "type": "object",
                        "description": "Agent definition object. Required for upsert. Must include at least 'name'.",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "If true, validate but do not persist (upsert/delete only).",
                        "default": False,
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        }

    @classmethod
    def result_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ok": {"type": "boolean"},
                "tool": {"type": "string"},
                "action": {"type": "string"},
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "agent_names": {"type": "array", "items": {"type": "string"}},
                "agent": {"type": ["object", "null"]},
                "error": {"type": ["object", "null"]},
            },
            "required": ["ok", "tool", "action"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # Shared-agent resolution
    # ------------------------------------------------------------------

    def _get_agent_manager(self, context: Dict[str, Any]) -> AgentManager:
        am = context.get("agent_manager")
        if am is not None:
            return am

        logger.warning(
            "agents_manage: no shared agent_manager in handler context; "
            "constructing a standalone instance. A reload on this instance "
            "will not refresh the live application's agent list."
        )
        agents_path = self.config.get("agents_path", "static/data/agents.json")
        strict = self.config.get("strict_agent_fields", True)
        return AgentManager(str(agents_path), strict_fields=strict)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def execute(self, args: Dict[str, Any], *, account_name: str = "auto", **context: Any) -> Dict[str, Any]:
        action = (args.get("action") or "").strip().lower()
        logger.info("agents_manage input account=%s action=%s", account_name, action)

        valid_actions = {"list", "get", "upsert", "delete", "reload"}
        if action not in valid_actions:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": {"code": "invalid_action", "message": f"Unknown action: {action}"},
            }

        try:
            am = self._get_agent_manager(context)

            if action == "list":
                return self._handle_list(am)
            if action == "get":
                return self._handle_get(am, args)
            if action == "upsert":
                return self._handle_upsert(am, args)
            if action == "delete":
                return self._handle_delete(am, args)
            if action == "reload":
                return self._handle_reload(am)

        except Exception as e:
            logger.exception("agents_manage failed action=%s", action)
            return {
                "ok": False,
                "tool": self.NAME,
                "action": action,
                "error": {"code": "internal_error", "message": str(e)},
            }

        return {
            "ok": False,
            "tool": self.NAME,
            "action": action,
            "error": {"code": "unknown", "message": "Unhandled code path"},
        }

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _handle_list(self, am: AgentManager) -> Dict[str, Any]:
        names = am.get_agent_names()
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "list",
            "count": len(names),
            "agent_names": names,
        }

    def _handle_get(self, am: AgentManager, args: Dict[str, Any]) -> Dict[str, Any]:
        name = (args.get("name") or "").strip()
        if not name:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "get",
                "error": {"code": "missing_name", "message": "name is required"},
            }

        agent = am.get_agent(name)
        if agent is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "get",
                "name": name,
                "error": {"code": "not_found", "message": f"Agent '{name}' not found"},
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "get",
            "name": name,
            "agent": agent.to_dict(),
        }

    def _handle_upsert(self, am: AgentManager, args: Dict[str, Any]) -> Dict[str, Any]:
        raw_agent = args.get("agent")
        if not isinstance(raw_agent, dict):
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "upsert",
                "error": {"code": "invalid_agent", "message": "agent must be an object with at least a 'name' field"},
            }

        if not (raw_agent.get("name") or "").strip():
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "upsert",
                "error": {"code": "missing_name", "message": "agent.name is required"},
            }

        validate_only = bool(args.get("validate_only", False))
        strict = self.config.get("strict_agent_fields", True)

        try:
            agent = Agent.from_dict(raw_agent, strict=strict)
        except Exception as e:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "upsert",
                "name": (raw_agent.get("name") or "").strip(),
                "error": {"code": "validation_error", "message": str(e)},
            }

        am.upsert_agent(agent)
        if not validate_only:
            am.save_agents()

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "upsert",
            "name": agent.name,
            "agent": agent.to_dict(),
        }

    def _handle_delete(self, am: AgentManager, args: Dict[str, Any]) -> Dict[str, Any]:
        name = (args.get("name") or "").strip()
        if not name:
            return {
                "ok": False,
                "tool": self.NAME,
                "action": "delete",
                "error": {"code": "missing_name", "message": "name is required"},
            }

        validate_only = bool(args.get("validate_only", False))
        removed = am.remove_agent(name)
        if removed and not validate_only:
            am.save_agents()

        return {
            "ok": True,
            "tool": self.NAME,
            "action": "delete",
            "name": name,
            "removed": removed,
        }

    def _handle_reload(self, am: AgentManager) -> Dict[str, Any]:
        am.load_agents()
        names = am.get_agent_names()
        return {
            "ok": True,
            "tool": self.NAME,
            "action": "reload",
            "count": len(names),
            "agent_names": names,
        }
