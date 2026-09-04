"""Handler for the tasklists_run tool.

Executes a persisted tasklist by delegating to AutomationProcessor.execute_tasklist().
Requires runtime context (conversation_id, primary_agent, account, etc.) passed
via **context kwargs from the FCP.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.message_processors.automation_processor import AutomationProcessor

logger = logging.getLogger(__name__)


class TasklistsRunHandler(HandlerV2):
    NAME = "tasklists_run"

    def __init__(self, config: ConfigManager):
        self.config = config
        self._automation_processor: Optional[AutomationProcessor] = None

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": "Execute a persisted tasklist by ID. Runs tasks sequentially and returns a summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasklist_id": {
                        "type": "string",
                        "description": "ID of the persisted tasklist to execute.",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["single-step", "multi-step"],
                        "description": "Execution mode: 'single-step' runs one task, 'multi-step' runs all pending tasks.",
                    },
                    "worker_agent": {
                        "type": "string",
                        "description": "Name of the worker agent to execute the tasklist as (e.g. colin, star). If not provided, uses the calling agent.",
                    },
                },
                "required": ["tasklist_id", "mode", "worker_agent"],
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
                "tasklist_id": {"type": "string"},
                "mode": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "object"},
                "worker_agent": {"type": ["string", "null"]},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        **context,
    ) -> Dict[str, Any]:
        tasklist_id = (args.get("tasklist_id") or "").strip()
        mode = (args.get("mode") or "single-step").strip()
        worker_agent_raw = args.get("worker_agent")
        worker_agent = (worker_agent_raw or "").strip() if worker_agent_raw is not None else None
        if worker_agent == "":
            worker_agent = None

        if not tasklist_id:
            return {
                "ok": False,
                "tool": self.NAME,
                "worker_agent": worker_agent,
                "error": {"code": "missing_tasklist_id", "message": "tasklist_id is required."},
            }

        if mode not in ("single-step", "multi-step"):
            return {
                "ok": False,
                "tool": self.NAME,
                "worker_agent": worker_agent,
                "error": {"code": "invalid_mode", "message": "mode must be 'single-step' or 'multi-step'."},
            }

        correlation_id = context.get("correlation_id")

        logger.info(
            "tasklists_run input account=%s tasklist_id=%s mode=%s worker_agent=%s correlation_id=%s",
            account_name,
            tasklist_id,
            mode,
            worker_agent,
            correlation_id,
        )

        # Resolve AutomationProcessor from context or via processor_factory.
        automation_processor: Optional[AutomationProcessor] = context.get("automation_processor")
        processor_factory = context.get("processor_factory")

        if automation_processor is None:
            # Fallback: try to build one from processor_factory (injector).
            if processor_factory is not None:
                try:
                    automation_processor = processor_factory.get("automation_processor")
                except Exception as e:
                    logger.exception("Failed to get AutomationProcessor from processor_factory")
                    return {
                        "ok": False,
                        "tool": self.NAME,
                        "worker_agent": worker_agent,
                        "error": {
                            "code": "missing_dependency",
                            "message": f"Cannot resolve AutomationProcessor via processor_factory: {e}",
                        },
                    }

        if automation_processor is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "worker_agent": worker_agent,
                "error": {
                    "code": "missing_dependency",
                    "message": (
                        "AutomationProcessor not available. "
                        "Ensure 'automation_processor' or 'processor_factory' is passed in context."
                    ),
                },
            }

        # Extract required execution context.
        primary_agent = context.get("primary_agent")
        account = context.get("account")
        conversation_id = context.get("conversation_id", "0")
        context_name = context.get("context_name", "")
        secondary_agent = context.get("secondary_agent")

        if primary_agent is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "worker_agent": worker_agent,
                "error": {
                    "code": "missing_context",
                    "message": "'primary_agent' is required in execution context.",
                },
            }
        if account is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "worker_agent": worker_agent,
                "error": {
                    "code": "missing_context",
                    "message": "'account' is required in execution context.",
                },
            }

        agent_name = (getattr(primary_agent, "name", "") or "").lower().strip()

        try:
            result = automation_processor.execute_tasklist(
                tasklist_id=tasklist_id,
                mode=mode,
                account_name=account_name,
                agent_name=agent_name,
                conversation_id=conversation_id,
                correlation_id=correlation_id,
                context_name="",
                primary_agent=primary_agent,
                account=account,
                secondary_agent=secondary_agent,
                processor_factory=processor_factory,
                worker_agent=worker_agent,
            )
            return {
                "ok": True,
                "tool": self.NAME,
                "tasklist_id": tasklist_id,
                "mode": mode,
                "correlation_id": correlation_id,
                "worker_agent": worker_agent,
                "result": result,
            }
        except Exception as e:
            logger.exception("tasklists_run execution failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "tasklist_id": tasklist_id,
                "mode": mode,
                "correlation_id": correlation_id,
                "worker_agent": worker_agent,
                "error": {"code": "execution_failed", "message": str(e)},
            }
