"""Delegate a task to an agent on an eligible Lucy machine."""

import json
import logging
from typing import Any, Dict, Optional

from galet import default_model_catalog

from src.agent import AgentManager
from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.handlers.remote_execute_handler import RemoteExecuteHandler
from src.machine_catalog import MachineConfigError, MachineDefinition, MachineManager


logger = logging.getLogger(__name__)


class DelegateTaskHandler(HandlerV2):
    """Select an execution machine and delegate through remote_execute."""

    NAME = "delegate_task"
    DEFAULT_TIMEOUT = RemoteExecuteHandler.DEFAULT_TIMEOUT

    def __init__(self, config: ConfigManager, agent_manager: AgentManager):
        self.config = config
        self.agent_manager = agent_manager

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Delegate a task to a named Lucy worker agent. Selects an "
                "eligible configured machine using the agent's resolved model "
                "policy plus optional capability and project requirements."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "Complete task instructions for the worker agent.",
                    },
                    "agentName": {
                        "type": "string",
                        "description": "Lucy worker agent that should perform the task.",
                    },
                    "capabilities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Machine capabilities required by the task.",
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional configured project required on the machine.",
                    },
                    "machine": {
                        "type": "string",
                        "description": "Optional machine override; empty selects automatically.",
                    },
                    "contextName": {
                        "type": "string",
                        "description": "Optional remote project context override.",
                    },
                    "accountName": {
                        "type": "string",
                        "description": "Optional remote account override.",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "description": "Timeout for the delegated request.",
                        "default": cls.DEFAULT_TIMEOUT,
                    },
                },
                "required": [
                    "task",
                    "agentName",
                    "capabilities",
                    "project",
                    "machine",
                    "contextName",
                    "accountName",
                    "timeout_seconds",
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
                "machine": {"type": "string"},
                "agent": {"type": "string"},
                "source": {"type": "string"},
                "model": {"type": "string"},
                "result": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
    ) -> Dict[str, Any]:
        task = self._text(args.get("task"))
        agent_name = self._text(args.get("agentName"))
        if not task:
            return self._error("task is required")
        if not agent_name:
            return self._error("agentName is required")

        capabilities = args.get("capabilities") or []
        if (
            not isinstance(capabilities, list)
            or any(not isinstance(item, str) or not item.strip() for item in capabilities)
        ):
            return self._error(
                "capabilities must be a list of non-empty strings",
                agent=agent_name,
            )
        capabilities = tuple(dict.fromkeys(item.strip() for item in capabilities))

        agent = self.agent_manager.get_agent(agent_name)
        if agent is None:
            available = ", ".join(sorted(self.agent_manager.get_agent_names())) or "(none)"
            return self._error(
                f"Unknown agent '{agent_name}'. Available agents: {available}",
                agent=agent_name,
            )

        try:
            resolved = default_model_catalog.resolve(agent.model_requirements())
        except (LookupError, ValueError) as exc:
            return self._error(
                f"Could not resolve model policy for agent '{agent_name}': {exc}",
                agent=agent_name,
            )

        project = self._text(args.get("project"))
        preferred_machine = self._text(args.get("machine"))
        manager = MachineManager.beside_config(self.config.file_name)
        try:
            manager.load()
        except MachineConfigError as exc:
            logger.warning("delegate_task: invalid machine catalog %s: %s", manager.path, exc)
            return self._error(f"Could not load machine catalog: {exc}", agent=agent_name)

        eligible = manager.eligible(
            agent=agent_name,
            source=resolved.source,
            model=resolved.model,
            project=project or None,
        )
        eligible = tuple(
            machine
            for machine in eligible
            if all(machine.supports(capability) for capability in capabilities)
        )

        machine = self._select_machine(eligible, preferred_machine)
        if machine is None:
            requirements = self._requirements(
                agent_name,
                resolved.source,
                resolved.model,
                capabilities,
                project,
                preferred_machine,
            )
            return self._error(
                f"No eligible machine found ({requirements}).",
                agent=agent_name,
                source=resolved.source,
                model=resolved.model,
            )

        context_name = self._text(args.get("contextName"))
        if not context_name and agent.default_context:
            context_name = str(agent.default_context).strip()

        transport = RemoteExecuteHandler(self.config)
        result = transport.execute(
            {
                "machine": machine.name,
                "question": task,
                "agentName": agent_name,
                "contextName": context_name,
                "accountName": self._text(args.get("accountName")),
                "timeout_seconds": args.get("timeout_seconds") or self.DEFAULT_TIMEOUT,
            },
            account_name=account_name,
        )
        return {
            **result,
            "tool": self.NAME,
            "agent": agent_name,
            "source": resolved.source,
            "model": resolved.model,
        }

    @staticmethod
    def _text(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    @staticmethod
    def _select_machine(
        eligible: tuple[MachineDefinition, ...],
        preferred: str,
    ) -> Optional[MachineDefinition]:
        if preferred:
            return next(
                (machine for machine in eligible if machine.name == preferred),
                None,
            )
        return eligible[0] if eligible else None

    @staticmethod
    def _requirements(
        agent: str,
        source: str,
        model: str,
        capabilities: tuple[str, ...],
        project: str,
        machine: str,
    ) -> str:
        values = [f"agent={agent}", f"model={source}/{model}"]
        if capabilities:
            values.append("capabilities=" + ",".join(capabilities))
        if project:
            values.append(f"project={project}")
        if machine:
            values.append(f"machine={machine}")
        return "; ".join(values)

    def _error(self, message: str, **extra: Any) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": False,
            "tool": self.NAME,
            "error": message,
        }
        result.update(extra)
        return result

    def execute_raw(
        self,
        arguments_raw: str,
        *,
        account_name: str = "auto",
        call_id: str = "",
        **context: Any,
    ) -> str:
        try:
            args = json.loads(arguments_raw or "{}")
        except Exception:
            args = {}
        result = self.execute(
            args if isinstance(args, dict) else {},
            account_name=account_name,
        )
        return json.dumps(result, ensure_ascii=False)
