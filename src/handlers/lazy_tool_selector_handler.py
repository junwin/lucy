"""lazy_tool_selector — scaffolding handler for validating lazy tool loading.

This is a *throwaway test rig*, not production code. Its only job is to
validate the Active-handler selection idea described in the "lazy tool
loading" requirement BEFORE we change the FunctionCallingProcessor.

The selection logic itself now lives in
``src/message_processors/lazy_tool_selection.py`` (shared with the FCP). This
handler is a thin wrapper that resolves the eligible set, calls the shared
selector, and reports token savings for offline probing.

Pipeline under test
--------------------
    Eligible handlers (static: registry ∩ agent.allowed_tools, narrowed by an explicit non-empty context list)
        ->  ask an LLM to pick the minimal Active set from the request text
        ->  apply the "three sisters" expansion heuristic
        ->  apply deterministic prompt-based rules
        ->  report token savings vs sending the full Eligible schema set.

Key idea
--------
The selection LLM call is given only a compact "name — description" menu
(NOT the full JSON schemas), so the extra call is cheap relative to the
savings of not sending every eligible schema body.

Offline batch probe (no FCP involved)
-------------------------------------
    python src/handlers/lazy_tool_selector_handler.py
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager
from src.handlers.handler_v2 import HandlerV2
from src.message_processors.lazy_tool_selection import select_active_tool_defs

logger = logging.getLogger(__name__)


class LazyToolSelectorHandler(HandlerV2):
    """Probe the lazy tool-loading idea and report token savings."""

    NAME = "lazy_tool_selector"

    def __init__(self, config: ConfigManager):
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
                "Scaffolding probe for lazy tool loading. Given a user request, "
                "ask an LLM to pick the minimal active tool subset from the "
                "eligible tools and report token savings vs sending all eligible "
                "schemas. Test rig only; not for production requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt_text": {
                        "type": "string",
                        "description": "The user request to test against.",
                    },
                    "model": {
                        "type": "string",
                        "description": "LLM model for the selection call.",
                        "default": "gpt-4o-mini",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Optional provider override (empty string = auto).",
                        "default": "",
                    },
                    "exclude_self": {
                        "type": "boolean",
                        "description": (
                            "Exclude this selector tool from the eligible set so it "
                            "cannot be chosen during testing. Avoids self-reference "
                            "noise. Default true."
                        ),
                        "default": True,
                    },
                    "prompt_style": {
                        "type": "string",
                        "enum": ["minimal", "verb_first"],
                        "description": (
                            "Selection prompt strategy. 'minimal' asks for the "
                            "minimal tool set. 'verb_first' maps action verbs to "
                            "tools using concrete action->tool examples."
                        ),
                        "default": "minimal",
                    },
                    "three_sisters": {
                        "type": "boolean",
                        "description": (
                            "Apply the 'three sisters' rule: if any of file_load, "
                            "file_save, or execute_command is selected, expand the "
                            "active set to include all three (when eligible). "
                            "Default true."
                        ),
                        "default": True,
                    },
                    "tasklist_pair": {
                        "type": "boolean",
                        "description": (
                            "Apply the 'tasklist pair' rule: if tasklists_manage "
                            "or tasklists_run is selected, include both (when "
                            "eligible). Default true."
                        ),
                        "default": True,
                    },
                    "rules": {
                        "type": "boolean",
                        "description": (
                            "Apply deterministic prompt-based rules (file_refs -> "
                            "three sisters, git_ops -> execute_command) on top of "
                            "the LLM pick. Default true."
                        ),
                        "default": True,
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
                "model": {"type": "string"},
                "exclude_self": {"type": "boolean"},
                "prompt_style": {"type": "string"},
                "three_sisters": {"type": "boolean"},
                "tasklist_pair": {"type": "boolean"},
                "rules_enabled": {"type": "boolean"},
                "rules_hits": {"type": "array", "items": {"type": "string"}},
                "rules_added": {"type": "array", "items": {"type": "string"}},
                "eligible_count": {"type": "integer"},
                "eligible_tools": {"type": "array", "items": {"type": "string"}},
                "selected_tools": {"type": "array", "items": {"type": "string"}},
                "selected_raw": {"type": "array", "items": {"type": "string"}},
                "selected_before_sisters": {"type": "array", "items": {"type": "string"}},
                "selected_before_rules": {"type": "array", "items": {"type": "string"}},
                "active_count": {"type": "integer"},
                "tokens": {"type": "object"},
                "active_tool_defs": {"type": "array", "items": {"type": "object"}},
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
        context_state: Any = None,
        **context: Any,
    ) -> Dict[str, Any]:
        prompt_text = (args.get("prompt_text") or "").strip()
        if not prompt_text:
            return {"ok": False, "tool": self.NAME, "error": "prompt_text is required"}

        model = (args.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
        provider = (args.get("provider") or "").strip() or None
        exclude_self = bool(args.get("exclude_self", True))
        prompt_style = (args.get("prompt_style") or "minimal").strip() or "minimal"
        three_sisters = bool(args.get("three_sisters", True))
        tasklist_pair = bool(args.get("tasklist_pair", True))
        rules_enabled = bool(args.get("rules", True))

        registry = context.get("registry")
        agent = context.get("primary_agent")

        eligible = self._resolve_eligible(registry, agent, context_state)
        if exclude_self:
            eligible = [td for td in eligible if td.get("name") != self.NAME]
        if not eligible:
            return {
                "ok": False,
                "tool": self.NAME,
                "error": (
                    "no eligible tools resolved "
                    + ("after excluding self" if exclude_self else "(check agent.allowed_tools)")
                ),
            }

        llm_adapter = context.get("llm_adapter")

        def _llm_call(messages: List[Dict[str, str]]) -> str:
            # Prefer the FCP's injected adapter so the test rig exercises the
            # exact same LLM call path as production. Fall back to RouterApi for
            # the offline __main__ probe (no adapter available there).
            if llm_adapter is not None:
                response = llm_adapter.call_model(
                    model=model,
                    input=messages,
                    temperature=0.0,
                    provider=provider,
                )
                return llm_adapter.get_text(response) or ""
            return self._call_selector(model, provider, messages)

        try:
            active_defs, meta = select_active_tool_defs(
                prompt_text=prompt_text,
                eligible_defs=eligible,
                llm_call=_llm_call,
                prompt_style=prompt_style,
                three_sisters=three_sisters,
                tasklist_pair=tasklist_pair,
                rules=rules_enabled,
                # Test rig: always run selection (never skip on size) and allow
                # empty results so under-selection is visible in the probe.
                min_eligible_to_select=4,
                allow_empty_active_set=True,
            )
        except Exception as exc:  # pragma: no cover - depends on live API
            logger.exception("lazy_tool_selector: selection LLM call failed")
            return {
                "ok": False,
                "tool": self.NAME,
                "error": f"selection LLM call failed: {type(exc).__name__}: {exc}",
            }

        return {
            "ok": True,
            "tool": self.NAME,
            "model": model,
            "exclude_self": exclude_self,
            "prompt_style": prompt_style,
            "three_sisters": three_sisters,
            "tasklist_pair": tasklist_pair,
            "rules_enabled": rules_enabled,
            "rules_hits": meta.get("rules_hits", []),
            "rules_added": meta.get("rules_added", []),
            "eligible_count": meta.get("eligible_count", len(eligible)),
            "eligible_tools": meta.get("eligible_tools", []),
            "selected_tools": meta.get("selected_tools", []),
            "selected_raw": meta.get("selected_raw", []),
            "selected_before_sisters": meta.get("selected_before_sisters", []),
            "selected_before_rules": meta.get("selected_before_rules", []),
            "active_count": meta.get("active_count", 0),
            "tokens": meta.get("tokens", {}),
            "active_tool_defs": active_defs,
        }

    # ------------------------------------------------------------------
    # resolution / selection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_eligible(
        registry: Any,
        agent: Any,
        context_state: Any,
    ) -> List[Dict[str, Any]]:
        """Resolve eligible tool defs.

        Uses the single-source-of-truth intersection:
        registry ∩ agent.allowed_tools, then narrowed only when the context
        carries a non-empty context.extra['allowed_tools'] list.
        """
        all_defs = registry.tools() if registry is not None else []
        by_name = {td.get("name"): td for td in all_defs}

        if registry is not None and hasattr(registry, "eligible_tool_defs"):
            return registry.eligible_tool_defs(agent, context_state)

        # Fallback (no registry available): static agent ceiling only.
        names = list(getattr(agent, "allowed_tools", None) or [])
        return [by_name[n] for n in names if n in by_name]

    def _call_selector(
        self, model: str, provider: Optional[str], messages: List[Dict[str, str]]
    ) -> str:
        # Lazy import: RouterApi pulls in provider SDKs (e.g. 'openai'), which
        # are optional and may be absent in minimal/test environments.
        from galet.router_api import RouterApi

        api = RouterApi()
        response = api.create_response(
            model=model,
            input=messages,
            temperature=0.0,
            provider=provider,
        )
        return (response.output_text or "").strip()


# ---------------------------------------------------------------------------
# Offline batch probe — run directly, no FCP involved.
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover - dev/test rig only
    import sys

    from src.handlers.registry_bootstrap import build_registry

    PROMPTS = [
        ("convert-32f-to-c", "What is 32F in centigrade?"),
        ("read-obsidian-note", "Read and check the obsidian note 'book/jamesJoyce.md'"),
        ("fix-github-issue", "Fix github issue #999 in the LLM module"),
        ("top-dividend-shares", "Give me the top 5 dividend shares"),
    ]

    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-4o-mini"
    handler = LazyToolSelectorHandler(config=None)  # type: ignore[arg-type]
    reg = build_registry()

    print(f"\n{'prompt':<22} {'elig':>4} {'act':>3} {'full':>6} {'active':>7} {'save%':>6} {'net':>6}")
    print("-" * 62)

    for slug, prompt in PROMPTS:
        result = handler.execute(
            {
                "prompt_text": prompt,
                "model": model,
                "provider": "",
                "exclude_self": True,
                "prompt_style": "verb_first",
                "three_sisters": True,
                "tasklist_pair": True,
                "rules": True,
            },
            registry=reg,
        )
        if not result.get("ok"):
            print(f"{slug:<22} ERROR: {result.get('error')}")
            continue
        t = result["tokens"]
        print(
            f"{slug:<22} {result['eligible_count']:>4} {result['active_count']:>3} "
            f"{t['eligible_schema_tokens']:>6} {t['active_schema_tokens']:>7} "
            f"{t['savings_pct']:>5}% {t['net_savings_tokens']:>6}"
        )
        print(f"    selected: {', '.join(result['selected_tools']) or '(none)'}")
        if result.get("rules_hits"):
            print(f"    rules: {', '.join(result['rules_hits'])} -> added {', '.join(result['rules_added'])}")
