"""Agent configuration model with robust loading and logging.

This module provides the Agent dataclass and helpers to construct instances
from raw dictionaries.

Design goals:
- Backward compatible with legacy field names.
- Helpful validation errors for missing/unknown fields.
- Unknown fields should *fail the offending agent* (so typos are caught),
  while AgentManager continues loading other agents.
- When strict=False (config toggle: strict_agent_fields), unknown fields
  log a warning and are stripped rather than raising ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from typing import Optional, List, Any, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    """Agent configuration.

    allowed_tools: Optional[List[str]]
        - If missing or None, no tools are allowed (strict intersection default).
        - If an empty list, no tools are allowed.
        - If a non-empty list, only the named tools are permitted for this agent.

    task_max_iterations: int
        - Budget per sub-task when decomposed via AutomationProcessor (default 10).
        - Separate from max_function_call_iterations so the agent keeps a high
          budget for orchestration but each sub-task gets a small, clean context.
    """

    name: str
    language_code: str = "en-US"
    context_type: str = "hybrid"  # previously select_type
    max_prompt_conversations: int = 6
    max_prompt_documents: int = 4
    temperature: float = 0.0
    save_responses: bool = True  # previously save_reposnses
    model: str = "gpt-5.1"
    message_processor: str = "function_calling_processor"
    max_function_call_iterations: int = 10
    task_max_iterations: int = 10
    partner_agent: Optional[str] = None
    system_prompt: str = ""
    style_prompt: str = ""
    persona: str = ""
    allowed_tools: Optional[List[str]] = None

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y", "on")
        try:
            return bool(int(value))
        except Exception:
            raise ValueError(f"Cannot coerce {value!r} to bool")

    @staticmethod
    def _format_unknown_fields_message(agent_name: Any, unknown_keys: set[str]) -> str:
        # Provide a helpful hint for common typos
        hints: list[str] = []
        if "allowed_tool" in unknown_keys or "allowed_toolz" in unknown_keys or "allow_tools" in unknown_keys:
            hints.append("Did you mean 'allowed_tools'?")
        if "save_reposnses" in unknown_keys:
            hints.append("Legacy key 'save_reposnses' is supported, but prefer 'save_responses'.")
        hint_str = (" " + " ".join(hints)) if hints else ""
        return (
            f"Agent '{agent_name}' contains unknown configuration fields: "
            f"{', '.join(sorted(unknown_keys))}." + hint_str
        )

    @staticmethod
    def from_dict(data: Dict[str, Any], strict: bool = True) -> "Agent":
        """Create an Agent from a raw dict, handling legacy field names.

        Args:
            data: Raw dictionary of agent configuration.
            strict: If True (default), unknown fields raise ValueError.
                    If False, unknown fields are logged as warnings and stripped.

        Behavior:
        - Missing required fields raise ValueError.
        - Unknown fields: hard-fail when strict=True, warn-and-strip when strict=False.
        - Some fields (e.g., allowed_tools) are validated/coerced where possible.

        Backward compatible with legacy keys:
        - 'select_type' -> 'context_type'
        - 'save_reposnses' -> 'save_responses'
        """
        if not isinstance(data, dict):
            raise TypeError("Agent.from_dict expects a dict")

        # Work on a shallow copy to avoid mutating the caller's dict
        raw = dict(data)

        # Handle legacy/alternate field names
        if "select_type" in raw and "context_type" not in raw:
            raw["context_type"] = raw.pop("select_type")
            logger.debug("Mapped legacy field 'select_type' -> 'context_type' for agent: %s", raw.get("name"))
        if "save_reposnses" in raw and "save_responses" not in raw:
            raw["save_responses"] = raw.pop("save_reposnses")
            logger.debug("Mapped legacy field 'save_reposnses' -> 'save_responses' for agent: %s", raw.get("name"))

        # Required field: name
        if "name" not in raw or not raw["name"]:
            raise ValueError("Agent configuration missing required 'name' field")

        agent_name = raw.get("name")

        # Determine allowed fields from the dataclass definition
        allowed_field_names = {f.name for f in dataclass_fields(Agent)}

        # Unknown fields: fail or warn depending on strict
        unknown_keys = set(raw.keys()) - allowed_field_names
        if unknown_keys:
            if strict:
                raise ValueError(Agent._format_unknown_fields_message(agent_name, unknown_keys))
            else:
                logger.warning(
                    "Agent '%s' contains unknown configuration fields: %s. "
                    "They will be ignored (strict_agent_fields=false).",
                    agent_name, ", ".join(sorted(unknown_keys)),
                )
                for key in unknown_keys:
                    raw.pop(key)

        # Validate/coerce specific fields to be forgiving where possible
        # allowed_tools: should be None or a list of strings
        atools = raw.get("allowed_tools", None)
        if atools is None:
            raw["allowed_tools"] = None
        elif isinstance(atools, list):
            cleaned: List[str] = []
            for i, v in enumerate(atools):
                if isinstance(v, str):
                    cleaned.append(v)
                else:
                    try:
                        cleaned.append(str(v))
                        logger.debug("Coerced allowed_tools[%d] to string for agent '%s'", i, agent_name)
                    except Exception:
                        raise ValueError(
                            f"Agent '{agent_name}' has invalid allowed_tools[{i}]={v!r}; expected string"
                        )
            raw["allowed_tools"] = cleaned
        else:
            # Be tolerant: if it's a comma-separated string, split; otherwise fail
            if isinstance(atools, str):
                split_tools = [s.strip() for s in atools.split(",") if s.strip()]
                raw["allowed_tools"] = split_tools
                logger.debug("Parsed allowed_tools string into list for agent '%s'", agent_name)
            else:
                raise ValueError(
                    f"Agent '{agent_name}' has invalid type for allowed_tools ({type(atools)}); expected list[str] or string"
                )

        # Numeric fields: coerce if possible, otherwise fail this agent (config is wrong)
        int_fields = [
            "max_prompt_conversations",
            "max_prompt_documents",
            "max_function_call_iterations",
            "task_max_iterations",
        ]
        for fname in int_fields:
            if fname in raw:
                val = raw[fname]
                if not isinstance(val, int):
                    try:
                        raw[fname] = int(val)
                        logger.debug("Coerced %s to int for agent '%s'", fname, agent_name)
                    except Exception:
                        raise ValueError(f"Agent '{agent_name}' has invalid {fname}={val!r}; expected int")

        if "temperature" in raw:
            val = raw["temperature"]
            if not isinstance(val, (int, float)):
                try:
                    raw["temperature"] = float(val)
                    logger.debug("Coerced temperature to float for agent '%s'", agent_name)
                except Exception:
                    raise ValueError(f"Agent '{agent_name}' has invalid temperature={val!r}; expected float")

        if "save_responses" in raw:
            try:
                raw["save_responses"] = Agent._coerce_bool(raw["save_responses"])
            except Exception:
                raise ValueError(
                    f"Agent '{agent_name}' has invalid save_responses={raw.get('save_responses')!r}; expected bool"
                )

        # Finally, construct Agent using only allowed fields (any missing fields will use dataclass defaults)
        try:
            return Agent(**raw)
        except TypeError as e:
            # Surface a helpful message
            logger.error("Failed to construct Agent from configuration for '%s': %s", agent_name, e)
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Serialize Agent to a dict suitable for JSON storage."""

        return {
            "name": self.name,
            "language_code": self.language_code,
            "context_type": self.context_type,
            "max_prompt_conversations": self.max_prompt_conversations,
            "max_prompt_documents": self.max_prompt_documents,
            "temperature": self.temperature,
            "save_responses": self.save_responses,
            "model": self.model,
            "message_processor": self.message_processor,
            "max_function_call_iterations": self.max_function_call_iterations,
            "task_max_iterations": self.task_max_iterations,
            "partner_agent": self.partner_agent,
            "system_prompt": self.system_prompt,
            "style_prompt": self.style_prompt,
            "persona": self.persona,
            "allowed_tools": self.allowed_tools,
        }

    def allows_tool(self, tool_name: str) -> bool:
        """Return True if the given tool is allowed for this agent.

        Rules (strict intersection):
        - allowed_tools is None => allow no tools
        - allowed_tools is [] => allow no tools
        - otherwise => allow only if tool_name is in allowed_tools
        """

        if not self.allowed_tools:
            return False
        return tool_name in self.allowed_tools
