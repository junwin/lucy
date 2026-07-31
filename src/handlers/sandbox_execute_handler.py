"""sandbox_execute handler — chain multiple tool calls in one step.

Lets the model emit a batch of sequential tool invocations.
Results from earlier steps are available to later steps via $step_N.field
variable substitution in args values.

Example:
  {"steps": [
    {"tool": "scrape_web_page",    "args": {"page_url": "https://..."}},
    {"tool": "get_keywords",       "args": {"content": "$step_1.result", "top_n": 5, "language_code": "en"}},
    {"tool": "file_save",          "args": {"path": "keywords.txt", "file_content": "$step_2.keywords"}}
  ]}

Returns: {ok, tool, steps: [{step, tool, ok, result...}, ...], final: <last result>}
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.handler_v2 import HandlerV2

logger = logging.getLogger(__name__)

_VAR_RE = re.compile(r"\$step_(\d+)\.(\S+)")


class SandboxExecuteHandler(HandlerV2):
    NAME = "sandbox_execute"

    def __init__(self, config: ConfigManager):
        self.config = config
        self._registry: Optional[HandlerRegistry] = None

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        # NOTE: strict mode is NOT enabled for this tool because the nested
        # `args` property is a free-form pass-through object that cannot
        # satisfy the `additionalProperties: false` requirement.  OpenAI's
        # Responses API refuses to accept the schema with strict=True.
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Execute a sequence of tool calls in one batch. "
                "Each step specifies a tool name and its arguments. "
                "Use $step_N.field to reference results from earlier steps "
                "(e.g., $step_1.result, $step_2.keywords). "
                "Use this to chain operations without returning to the LLM between each step. "
                "Set continue_on_error=true to keep running even if a step fails "
                "(useful for scraping multiple URLs where some may fail)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "description": "List of tool calls to execute sequentially.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tool": {
                                    "type": "string",
                                    "description": "Name of the tool to call (e.g., scrape_web_page, get_keywords, file_save, execute_command).",
                                },
                                "args": {
                                    "type": "object",
                                    "description": "Arguments for the tool. Use $step_N.field to reference earlier results.",
                                },
                            },
                            "required": ["tool", "args"],
                            "additionalProperties": False,
                        },
                    },
                    "continue_on_error": {
                        "type": "boolean",
                        "description": "If true, continue executing remaining steps even if a step fails. Default false (stop on first error).",
                        "default": False,
                    },
                },
                "required": ["steps"],
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
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "integer"},
                            "tool": {"type": "string"},
                            "ok": {"type": "boolean"},
                            "result": {"type": "object"},
                        },
                    },
                },
                "final": {"type": "object"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # Variable substitution
    # ------------------------------------------------------------------

    def _resolve_vars(self, value: Any, step_results: Dict[int, Dict[str, Any]]) -> Any:
        """Replace $step_N.field references in a string or recurse into dict/list."""
        if isinstance(value, str):
            def _replace(m: re.Match) -> str:
                step_idx = int(m.group(1))
                field_path = m.group(2)
                step_result = step_results.get(step_idx, {})
                val: Any = step_result
                for part in field_path.split("."):
                    if isinstance(val, dict):
                        val = val.get(part)
                    elif isinstance(val, list):
                        try:
                            val = val[int(part)]
                        except (ValueError, IndexError):
                            return m.group(0)
                    else:
                        return m.group(0)
                if val is None:
                    return ""
                if isinstance(val, (dict, list)):
                    return json.dumps(val, ensure_ascii=False)
                return str(val)

            return _VAR_RE.sub(_replace, value)

        if isinstance(value, dict):
            return {k: self._resolve_vars(v, step_results) for k, v in value.items()}

        if isinstance(value, list):
            return [self._resolve_vars(item, step_results) for item in value]

        return value

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        registry: Optional[HandlerRegistry] = None,
        **context: Any,
    ) -> Dict[str, Any]:
        reg: Optional[HandlerRegistry] = registry or self._registry
        if reg is None:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "No HandlerRegistry available. The sandbox_execute tool must have access to the registry.",
            }

        steps_raw = args.get("steps")
        if not isinstance(steps_raw, list) or len(steps_raw) == 0:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "steps must be a non-empty array of {tool, args} objects.",
            }

        continue_on_error = bool(args.get("continue_on_error", False))

        step_results: Dict[int, Dict[str, Any]] = {}
        step_outputs: List[Dict[str, Any]] = []
        overall_ok = True

        for i, step in enumerate(steps_raw, start=1):
            if not isinstance(step, dict):
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "error": f"Step {i} is not an object.",
                }

            tool_name = (step.get("tool") or "").strip()
            step_args = step.get("args")
            if not tool_name:
                return {
                    "ok": False,
                    "tool": self.NAME,
                    "error": f"Step {i} has no tool name.",
                }
            if not isinstance(step_args, dict):
                step_args = {}

            # Resolve variables from earlier steps
            resolved_args = self._resolve_vars(step_args, step_results)

            logger.info(
                "sandbox_execute: step %d/%d tool=%s args_keys=%s",
                i,
                len(steps_raw),
                tool_name,
                list(resolved_args.keys()),
            )

            # Try to get the handler
            try:
                handler = reg.create(tool_name, config=self.config)
            except KeyError:
                tool_result = {
                    "ok": False,
                    "tool": tool_name,
                    "error": f"Unknown tool: {tool_name}",
                }
                step_results[i] = tool_result
                step_outputs.append({
                    "step": i,
                    "tool": tool_name,
                    "ok": False,
                    "result": tool_result,
                })
                overall_ok = False
                if not continue_on_error:
                    break
                continue

            try:
                # Only pass account_name — child handlers don't accept registry or extra kwargs
                tool_result = handler.execute(
                    resolved_args,
                    account_name=account_name,
                )
            except Exception as e:
                logger.exception("sandbox_execute: step %d tool=%s failed", i, tool_name)
                tool_result = {
                    "ok": False,
                    "tool": tool_name,
                    "error": f"{type(e).__name__}: {e}",
                }

            step_results[i] = tool_result

            step_ok = bool(tool_result.get("ok")) if isinstance(tool_result, dict) else False
            if not step_ok:
                overall_ok = False

            step_outputs.append({
                "step": i,
                "tool": tool_name,
                "ok": step_ok,
                "result": tool_result,
            })

            if not step_ok and not continue_on_error:
                break

        final = step_outputs[-1].get("result", {}) if step_outputs else {}

        return {
            "ok": overall_ok,
            "tool": self.NAME,
            "steps": step_outputs,
            "final": final,
        }
