"""tool_selection_probe — diagnostic handler for the tool selection pipeline (issue #126).

Wraps ``ToolSelectionPipeline.resolve()`` (``src/tool_selection/pipeline.py``,
approved design ``software/ai/lucy/design/tool-selection-pipeline.md`` §3/§5)
as a HandlerV2 tool so the pipeline can be probed offline / from a chat
without invoking the function-calling loop: given a prompt (plus optional
account/context overrides), it reports the resolved ``allowed``,
``all_tools``, ``eligible``, ``required``, ``prompt_based`` and ``active``
stages plus the pipeline ``meta``.

The pipeline is built from the handler execution context (the same keys the
FunctionCallingProcessor injects into ``_execute_tool_calls``):

- ``registry`` — the ``HandlerRegistry`` (``context['registry']``).
- ``storage`` — ``context['storage']``, falling back to
  ``context['prompt_builder'].storage`` when the processor did not inject
  one (design doc §5.3 / FCP ``load_context_state`` convention).
- ``llm_adapter`` — ``context['llm_adapter']`` (used only for the stage-6
  selection LLM; never resolved when selection is disabled/below threshold).
- ``config`` — ``self.config`` (the handler is created by
  ``registry.create(config=...)``).
- ``agent`` — ``context['primary_agent']``.

``account_name`` / ``context_name`` come from the tool args when provided,
falling back to the request-level values (the ``account_name`` keyword
passed to ``execute``, and ``context['context_name']``).

``ToolSelectionError`` is caught and surfaced as a structured
``{ok: false, code, message}`` result (design doc §6 — hard, user-facing
error; the LLM is never invoked in that case).
"""

from __future__ import annotations

from typing import Any, Dict

from src.handlers.handler_v2 import HandlerV2
from src.tool_selection import ToolSelectionError, ToolSelectionPipeline

__all__ = ["ToolSelectionProbeHandler"]


class ToolSelectionProbeHandler(HandlerV2):
    """Probe the tool selection pipeline and report every resolved stage."""

    NAME = "tool_selection_probe"

    def __init__(self, config: Any):
        # Keep signature compatible with registry.create(config=...).
        self.config = config

    # ------------------------------------------------------------------
    # HandlerV2 contract
    # ------------------------------------------------------------------

    @classmethod
    def name(cls) -> str:
        return cls.NAME

    @classmethod
    def tool_def(cls) -> Dict[str, Any]:
        return {
            "type": "function",
            "name": cls.NAME,
            "description": (
                "Diagnostic probe for the tool selection pipeline. Given a "
                "user prompt, resolve the allowed / eligible / required / "
                "prompt-based / active tool sets exactly as the "
                "function-calling loop would (without invoking it) and "
                "report them plus pipeline metadata. Probe only; not for "
                "production requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The user request to resolve tool selection for.",
                    },
                    "account_name": {
                        "type": "string",
                        "description": (
                            "Account name for the context lookup. Defaults to "
                            "the request's account."
                        ),
                    },
                    "context_name": {
                        "type": "string",
                        "description": (
                            "Context name for the required_tools lookup. "
                            "Defaults to the request's context; 'none' means "
                            "no context."
                        ),
                    },
                },
                "required": ["prompt_text"],
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
                "allowed": {"type": "array", "items": {"type": "string"}},
                "all_tools": {"type": "array", "items": {"type": "string"}},
                "eligible": {"type": "array", "items": {"type": "string"}},
                "required": {"type": "array", "items": {"type": "string"}},
                "prompt_based": {"type": "array", "items": {"type": "string"}},
                "active": {"type": "array", "items": {"type": "string"}},
                "meta": {"type": "object"},
                "code": {"type": "string"},
                "message": {"type": "string"},
                "error": {"type": "string"},
            },
            "required": ["ok", "tool"],
            "additionalProperties": True,
        }

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(
        self,
        args: Dict[str, Any],
        *,
        account_name: str = "auto",
        **context: Any,
    ) -> Dict[str, Any]:
        prompt_text = (args.get("prompt_text") or "").strip()
        if not prompt_text:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": "prompt_text is required",
            }

        # Resolve the pipeline collaborators from the handler context (the
        # same keys the FunctionCallingProcessor injects into
        # _execute_tool_calls).
        registry = context.get("registry")
        storage = context.get("storage")
        if storage is None:
            prompt_builder = context.get("prompt_builder")
            storage = getattr(prompt_builder, "storage", None)
        llm_adapter = context.get("llm_adapter")
        agent = context.get("primary_agent")

        # account_name/context_name: tool args win, then request-level values.
        resolved_account = (args.get("account_name") or "").strip() or account_name or "auto"
        resolved_context = (
            (args.get("context_name") or "").strip()
            or (context.get("context_name") or "").strip()
            or ""
        )

        pipeline = ToolSelectionPipeline(
            registry=registry,
            storage=storage,
            llm_adapter=llm_adapter,
            config=self.config,
        )

        try:
            result = pipeline.resolve(
                agent=agent,
                account_name=resolved_account,
                context_name=resolved_context,
                prompt_text=prompt_text,
            )
        except ToolSelectionError as exc:
            # Design doc §6: hard, user-facing error — never silently skipped.
            return {
                "ok": False,
                "tool": self.NAME,
                "code": exc.code,
                "message": exc.message,
            }

        # Strip full tool schemas (meta["active_defs"]) so the probe result
        # stays compact: tool names only, plus small scalar metadata.
        meta = dict(result.meta)
        meta.pop("active_defs", None)

        return {
            "ok": True,
            "tool": self.NAME,
            "allowed": result.allowed,
            "all_tools": result.all_tools,
            "eligible": result.eligible,
            "required": result.required,
            "prompt_based": result.prompt_based,
            "active": result.active,
            "meta": meta,
        }
