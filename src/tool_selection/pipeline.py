from __future__ import annotations
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from . import selection
from .errors import ToolSelectionError

__all__ = [
    "ToolSelection",
    "ToolSelectionPipeline",
    "get_agent_allowed_tools",
    "get_all_tools_from_registry",
    "get_required_tools",
]

_SELECTION_MODEL_FALLBACK = "gpt-4o-mini"
DEFAULT_MAX_HANDLER_SCHEMA_TOKENS = 8000
_PROVIDER_PREFIXES = (
    ("deepseek", "deepseek"),
    ("mistral", "mistral"),
    ("ollama", "ollama"),
    ("gpt", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
)

@dataclass(frozen=True)
class ToolSelection:
    allowed: List[str]
    all_tools: List[str]
    eligible: List[str]
    required: List[str]
    prompt_based: List[str]
    active: List[str]
    meta: Dict[str, Any]

def get_agent_allowed_tools(agent) -> List[str]:
    allowed = getattr(agent, "allowed_tools", None)
    if not allowed:
        return []
    return list(allowed)

def get_all_tools_from_registry(registry) -> List[str]:
    return [td.get("name") for td in registry.tools() if td.get("name")]

def get_required_tools(storage, account_name: str, context_name: str) -> List[str]:
    context = _load_context(storage, account_name, context_name)
    if context is None:
        return []
    raw = getattr(context, "required_tools", None)
    if raw is None:
        return []
    if isinstance(raw, (str, bytes)):
        return []
    try:
        items = list(raw)
    except Exception:
        return []
    normalized: List[str] = []
    for item in items:
        if item is None:
            continue
        name = str(item).strip()
        if name:
            normalized.append(name)
    return _order_preserving_dedupe(normalized)

class LLMResolver:
    def __init__(self, config, agent, llm_adapter):
        self.config = config
        self.agent = agent
        self.llm_adapter = llm_adapter

    def resolve(self) -> Tuple[str, Optional[str]]:
        if self.llm_adapter is None:
            raise ValueError("llm_adapter is None")

        ts_cfg = _config_section(self.config, "tool_selection")
        ltl_cfg = _config_section(self.config, "lazy_tool_loading")

        model = _first_non_empty(
            ts_cfg.get("llm_model"),
            ltl_cfg.get("model"),
            getattr(self.agent, "model", None),
        ) or _SELECTION_MODEL_FALLBACK

        provider = _first_non_empty(
            ts_cfg.get("llm_provider"),
            ltl_cfg.get("provider"),
            getattr(self.agent, "provider", None),
        )

        source = str(ts_cfg.get("llm_source") or "router").strip().lower() or "router"
        if source not in ("router", "direct"):
            source = "router"

        if source == "direct" and not provider:
            provider = _infer_provider(model)

        return model, provider

    def call_llm(self, messages: List[Dict[str, str]], model: str, provider: Optional[str]) -> str:
        response = self.llm_adapter.call_model(
            model=model,
            input=messages,
            temperature=0.0,
            provider=provider,
        )
        return self.llm_adapter.get_text(response) or ""

class ToolSelectionPipeline:
    def __init__(self, registry, storage, llm_adapter, config):
        self.registry = registry
        self.storage = storage
        self.llm_adapter = llm_adapter
        self.config = config

    def resolve(self, agent, account_name: str, context_name: str, prompt_text: str) -> ToolSelection:
        meta: Dict[str, Any] = {}

        allowed = get_agent_allowed_tools(agent)
        all_tools = get_all_tools_from_registry(self.registry) if self.registry is not None else []
        registry_names = set(all_tools)
        allowed_set = set(allowed)
        eligible = [name for name in all_tools if name in allowed_set]
        required = get_required_tools(self.storage, account_name, context_name)
        _validate_required(required, allowed_set, registry_names)

        should_select, skip_meta = self._should_select_prompt_based(eligible)
        if should_select:
            prompt_based, selection_meta = self._select_prompt_based(prompt_text, agent, eligible)
        else:
            prompt_based = []
            selection_meta = skip_meta
        meta["selection"] = selection_meta
        if selection_meta.get("error"):
            meta["selection_error"] = selection_meta["error"]

        if selection_meta.get("skipped"):
            active = list(eligible)
        else:
            active = _order_preserving_dedupe(required + prompt_based)
        active_defs = self._defs_by_name(active)
        meta["active_defs"] = active_defs

        cap = _resolve_schema_cap(self.config)
        tokens = _schema_tokens(active_defs)
        meta["schema_tokens"] = tokens
        meta["schema_cap"] = cap
        if cap is not None and tokens > cap:
            raise ToolSelectionError("budget_exceeded", active)

        return ToolSelection(
            allowed=allowed,
            all_tools=all_tools,
            eligible=eligible,
            required=required,
            prompt_based=prompt_based,
            active=active,
            meta=meta,
        )

    def get_tool_handler_defs(self, agent, account_name: str, context_name: str, prompt_text: str) -> List[Dict[str, Any]]:
        selection = self.resolve(agent, account_name, context_name, prompt_text)
        return self._defs_by_name(selection.active)

    def _should_select_prompt_based(self, eligible: List[str]) -> Tuple[bool, Dict[str, Any]]:
        ltl_cfg = _config_section(self.config, "lazy_tool_loading")
        enabled = bool(ltl_cfg.get("enabled", False))
        if not enabled:
            return False, {"skipped": True, "reason": "disabled"}

        min_eligible = _as_int(ltl_cfg.get("min_eligible_to_select"), 5)
        if len(eligible) < min_eligible:
            return False, {
                "skipped": True,
                "reason": "below_threshold",
                "min_eligible_to_select": min_eligible,
                "eligible_count": len(eligible),
            }

        return True, {}

    def _select_prompt_based(self, prompt_text: str, agent, eligible: List[str]) -> Tuple[List[str], Dict[str, Any]]:
        eligible_defs = self._defs_by_name(eligible)
        try:
            resolver = LLMResolver(self.config, agent, self.llm_adapter)
            model, provider = resolver.resolve()
            llm_call = lambda messages: resolver.call_llm(messages, model, provider)
            prompt_based = query_llm(prompt_text, eligible_defs, llm_call=llm_call, model=model, provider=provider, config=self.config)
        except Exception as exc:
            logging.warning(f"tool_selection: prompt-based selection failed; falling back to required-only: {exc}")
            return [], {"skipped": False, "error": f"{type(exc).__name__}: {exc}"}

        return prompt_based, {
            "skipped": False,
            "model": model,
            "provider": provider,
            "prompt_style": _resolve_prompt_style(self.config),
            "eligible_count": len(eligible),
            "suggested": prompt_based,
        }

    def _defs_by_name(self, names: List[str]) -> List[Dict[str, Any]]:
        if self.registry is None:
            return []
        by_name = {td.get("name"): td for td in self.registry.tools() if td.get("name")}
        return [by_name[name] for name in names if name in by_name]

def query_llm(
    prompt_text: str,
    eligible_defs: List[Dict[str, Any]],
    *,
    llm_call,
    model: str,
    provider: Optional[str],
    config,
) -> List[str]:
    prompt_style = _resolve_prompt_style(config)
    selected, _meta = selection.suggest_tools(
        prompt_text,
        eligible_defs,
        llm_call=llm_call,
        model=model,
        provider=provider,
        prompt_style=prompt_style,
    )
    return selected

def _resolve_prompt_style(config) -> str:
    ts_cfg = _config_section(config, "tool_selection")
    ltl_cfg = _config_section(config, "lazy_tool_loading")
    return _first_non_empty(ts_cfg.get("prompt_style"), ltl_cfg.get("prompt_style")) or "verb_first"

def _validate_required(required: List[str], allowed_set: set, registry_names_set: set) -> None:
    if not required:
        return
    missing_permission = [name for name in required if name not in allowed_set]
    if missing_permission:
        raise ToolSelectionError("required_not_permissioned", missing_permission)
    missing_registered = [name for name in required if name not in registry_names_set]
    if missing_registered:
        raise ToolSelectionError("required_not_registered", missing_registered)

def _schema_tokens(function_defs: List[Dict[str, Any]]) -> int:
    if not function_defs:
        return 0
    try:
        text = json.dumps(function_defs, ensure_ascii=False)
    except Exception:
        return 0
    return max(1, len(text) // 4)

def _resolve_schema_cap(config) -> Optional[int]:
    if config is not None:
        try:
            raw = config.get("max_handler_schema_tokens", None)
            if raw is not None:
                value = int(raw)
                if value > 0:
                    return value
                if value <= 0:
                    return None
        except Exception:
            pass
    return DEFAULT_MAX_HANDLER_SCHEMA_TOKENS

def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _first_non_empty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None

def _config_section(config, key: str) -> Dict[str, Any]:
    if config is None:
        return {}
    value = None
    if hasattr(config, "get"):
        try:
            value = config.get(key)
        except Exception:
            return {}
    elif isinstance(config, dict):
        value = config.get(key)
    if isinstance(value, dict):
        return value
    return {}

def _infer_provider(model: str) -> Optional[str]:
    name = (model or "").strip().lower()
    for prefix, provider in _PROVIDER_PREFIXES:
        if name.startswith(prefix):
            return provider
    return "openai"

def _load_context(storage, account_name: str, context_name: str) -> Optional[Any]:
    if storage is None:
        return None
    if not context_name or str(context_name).strip().lower() == "none":
        return None

    get_or_create = getattr(storage, "get_or_create_context", None)
    if callable(get_or_create):
        try:
            context = get_or_create(account_name, context_name)
            if context is not None:
                return context
        except Exception:
            logging.warning(f"tool_selection: get_or_create_context({account_name}, {context_name}) failed; falling back to get_context")

    get_ctx = getattr(storage, "get_context", None)
    if callable(get_ctx):
        try:
            return get_ctx(account_name, context_name)
        except Exception:
            logging.warning(f"tool_selection: get_context({account_name}, {context_name}) failed; no required tools")
            return None
    return None

def _order_preserving_dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
