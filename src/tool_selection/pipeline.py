"""Tool selection pipeline: data model, stage helpers, and orchestrator (issue #126).

Part of the approved design (``software/ai/lucy/design/tool-selection-pipeline.md``,
sections 3, 5.1, and 5.5). This module currently provides:

- ``ToolSelection`` — the frozen result dataclass the pipeline returns
  (pure data, easy to assert in tests).
- ``ToolSelectionPipeline`` — the orchestrator: ``resolve()`` wires the
  stage helpers (allowed → all_tools → eligible → required → validate →
  prompt_based → finalize → budget) and records every stage in ``meta``.
- ``get_agent_allowed_tools`` — stage 1 of the pipeline: normalize the
  agent's ``allowed_tools`` into a plain list of tool names.
- ``get_all_tools_from_registry`` — stage 2 of the pipeline: every
  registered tool handler name, in registry order (the full candidate set
  before any agent filtering).
- ``get_required_tools`` — stage 4 of the pipeline: the context's
  ``required_tools`` (own ``mandatory_tools`` + resolved skills'
  ``mandatory_tools``), loaded from the injected storage and normalized.
- ``resolve_llm_target`` — resolve how the stage-6 selection LLM
  (``query_llm``) gets its callable: injected ``llm_adapter`` plus the
  agent's model/provider, with ``tool_selection.*`` config overrides.
- ``query_llm`` — stage 6 of the pipeline: build the compact selection
  prompt from the eligible tool defs and ask the LLM (via
  ``selection.suggest_tools``) for the minimal prompt-based tool names.

Deliberately lean: no storage or LLM imports (the storage object is
duck-typed — any object exposing ``get_or_create_context`` / ``get_context``
works, and the registry is duck-typed — any object exposing ``tools()``).
The only intra-package imports are ``selection`` (same package, stage 6)
and ``errors`` (same package, ``ToolSelectionError``).
``allowed_tools`` is a *permission*, not a mandate (design doc §4):
``None`` or empty means the agent may use 0 tools.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import selection
from .errors import ToolSelectionError

__all__ = [
    "ToolSelection",
    "ToolSelectionPipeline",
    "get_agent_allowed_tools",
    "get_all_tools_from_registry",
    "get_required_tools",
    "query_llm",
    "resolve_llm_target",
]

# Fallback selection model when neither config nor the agent specify one.
# Matches the FCP's historical default for the lazy-selection LLM call.
_SELECTION_MODEL_FALLBACK = "gpt-4o-mini"

# Fallback schema budget when config does not set max_handler_schema_tokens.
# Parity with the FCP's DEFAULT_MAX_HANDLER_SCHEMA_TOKENS.
DEFAULT_MAX_HANDLER_SCHEMA_TOKENS = 8000

# Model-name prefix -> provider, mirroring ``src.llm.provider_registry.PREFIX_MAP``
# (checked in order) so ``llm_source='direct'`` can pin a backend without
# importing ``src.llm``. Kept local to stay dependency-free.
_PROVIDER_PREFIXES: Tuple[Tuple[str, str], ...] = (
    ("deepseek", "deepseek"),
    ("mistral", "mistral"),
    ("ollama", "ollama"),
    ("gpt", "openai"),
    ("o1", "openai"),
    ("o3", "openai"),
)


@dataclass(frozen=True)
class ToolSelection:
    """Result of the tool-selection pipeline (design doc §5.1).

    All fields are plain tool names (or a meta dict), so the dataclass is
    pure data and trivially assertable in tests.

    Attributes:
        allowed: step 1 — the agent's permissioned tools
            (``agent.allowed_tools``, normalized; empty means no tools).
        all_tools: step 2 — all registered handler names, registry order.
        eligible: step 3 — ``allowed ∩ all``, registry order.
        required: step 4 — ``context.required_tools``, deduplicated.
        prompt_based: step 6 — tools the LLM suggested, clamped to eligible.
        active: step 7 — final set sent to the model
            (``required ∪ prompt_based``, deduplicated; the full eligible set
            when selection was skipped).
        meta: pipeline metadata (skip reason, selection error, budget notes,
            resolved active defs).
    """

    allowed: List[str]
    all_tools: List[str]
    eligible: List[str]
    required: List[str]
    prompt_based: List[str]
    active: List[str]
    meta: Dict[str, Any]


def get_agent_allowed_tools(agent) -> List[str]:
    """Normalize ``agent.allowed_tools`` into a plain list of tool names.

    ``allowed_tools`` is a permission, not a mandate (design doc §4):

    - ``None`` or empty (``[]``) → the agent may use 0 tools; return ``[]``.
    - otherwise → returned as a plain list, preserving order.

    No registry, storage, or LLM interaction happens here.
    """
    allowed = getattr(agent, "allowed_tools", None)
    if not allowed:
        return []
    return list(allowed)


def get_all_tools_from_registry(registry) -> List[str]:
    """Return every registered tool handler name, in registry order.

    Stage 2 of the pipeline (design doc §3): the full candidate set before
    any agent filtering. Reads the registry's ``tools()`` — a list of tool
    def dicts in registry (insertion) order — and extracts each ``name``.
    The registry is duck-typed: any object exposing ``tools() -> list[dict]``
    works (the real ``HandlerRegistry``, or a fake in tests).

    No agent, storage, or LLM interaction happens here.
    """
    return [td.get("name") for td in registry.tools() if td.get("name")]


def get_required_tools(storage, account_name: str, context_name: str) -> List[str]:
    """Return the context's required tools (stage 4 of the pipeline).

    Reads ``context.required_tools`` from the injected storage object — the
    aggregated ``mandatory_tools`` + each resolved skill's ``mandatory_tools``
    (design doc §3 step 4, §5.3). The context is loaded with the same
    fallback the prompt builder uses: prefer ``get_or_create_context``, else
    ``get_context``, else ``None`` (no context ⇒ no required tools).

    The result is normalized: names are coerced to strings, whitespace is
    stripped, empty entries are dropped, and duplicates are removed
    preserving first-occurrence order. The storage is duck-typed: any object
    exposing ``get_or_create_context`` and/or ``get_context`` works (the real
    storage, or a fake in tests).

    No registry or LLM interaction happens here; this never raises — storage
    errors or a missing context yield an empty list (fail-soft, matching the
    FCP's ``load_context_state`` convention).
    """
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


def resolve_llm_target(
    config,
    agent,
    llm_adapter,
) -> Tuple[Callable[[List[Dict[str, str]]], str], str, Optional[str]]:
    """Resolve how ``query_llm`` gets its LLM: ``(llm_call, model, provider)``.

    Returns a tuple:

    - ``llm_call(messages) -> str`` — a callable that sends the stage-6
      selection messages (list of ``{"role": ..., "content": ...}`` dicts)
      to the LLM and returns the raw reply text (via the adapter's
      ``get_text``). Exceptions from the underlying LLM propagate — the
      pipeline owns the D5 required-only fallback.
    - ``model`` — the resolved model name.
    - ``provider`` — the resolved provider name, or ``None`` when the
      adapter's router should infer the backend from the model name.

    Defaults (design doc §5.3): the injected ``llm_adapter`` plus the
    agent's ``model`` / ``provider``.

    Config overrides — new keys under ``tool_selection`` (highest
    precedence):

    - ``tool_selection.llm_model`` — override the selection model.
    - ``tool_selection.llm_provider`` — override the selection provider.
    - ``tool_selection.llm_source`` — ``'router'`` (default) or ``'direct'``:

      * ``'router'`` — call ``llm_adapter.call_model(model=..., provider=...)``
        and let the adapter's internal RouterApi resolve the backend from the
        model name (or the explicit provider). This is the FCP's existing
        lazy-selection behaviour.
      * ``'direct'`` — pin the provider explicitly: when no provider is
        configured, infer one from the model name (deepseek / mistral /
        ollama / openai-style prefixes, default ``openai``) so the backend is
        fixed at resolve time instead of per-call routing.

    Backward-compatible fallbacks (between the new keys and the agent
    defaults, matching today's ``config.json``): ``lazy_tool_loading.model``
    and ``lazy_tool_loading.provider`` (design doc §5.3).

    The adapter is duck-typed: any object exposing ``call_model(...)`` and
    ``get_text(...)`` works (the real ``LLMAdapter``, or a fake in tests).

    Raises ValueError when ``llm_adapter`` is ``None`` (the pipeline cannot
    call an LLM without an adapter).
    """
    if llm_adapter is None:
        raise ValueError(
            "resolve_llm_target: llm_adapter is None; the selection LLM "
            "cannot be called without an injected LLM adapter"
        )

    ts_cfg = _config_section(config, "tool_selection")
    ltl_cfg = _config_section(config, "lazy_tool_loading")

    # Model precedence: tool_selection.llm_model > lazy_tool_loading.model
    # > agent.model > fallback. Blank/whitespace values fall through.
    model = _first_non_empty(
        ts_cfg.get("llm_model"),
        ltl_cfg.get("model"),
        getattr(agent, "model", None),
    ) or _SELECTION_MODEL_FALLBACK

    # Provider precedence: tool_selection.llm_provider
    # > lazy_tool_loading.provider > agent.provider (may stay None).
    provider = _first_non_empty(
        ts_cfg.get("llm_provider"),
        ltl_cfg.get("provider"),
        getattr(agent, "provider", None),
    )

    # Source: tool_selection.llm_source in {'router', 'direct'}; unknown -> 'router'.
    source = str(ts_cfg.get("llm_source") or "router").strip().lower() or "router"
    if source not in ("router", "direct"):
        source = "router"

    if source == "direct" and not provider:
        provider = _infer_provider(model)

    def llm_call(messages: List[Dict[str, str]]) -> str:
        response = llm_adapter.call_model(
            model=model,
            input=messages,
            temperature=0.0,
            provider=provider,
        )
        return llm_adapter.get_text(response) or ""

    return llm_call, model, provider


def query_llm(
    prompt_text: str,
    eligible_defs: List[Dict[str, Any]],
    *,
    llm_target: Tuple[Callable[[List[Dict[str, str]]], str], str, Optional[str]],
    config,
) -> List[str]:
    """Ask the selection LLM for the prompt-based tools (stage 6).

    Uses the LLM target resolved by ``resolve_llm_target`` — the tuple
    ``(llm_call, model, provider)`` — to build the compact "name — first
    sentence" menu from ``eligible_defs`` and call ``selection.suggest_tools``.
    Returns the suggested tool names, already clamped to the eligible set and
    deduplicated (eligible order preserved) by ``selection.py``; empty when
    the LLM suggests nothing.

    ``config`` only feeds the prompt style: ``tool_selection.prompt_style``,
    falling back to ``lazy_tool_loading.prompt_style`` (matching the FCP's
    existing lazy-selection behaviour), defaulting to ``'verb_first'``.

    LLM failures are NOT swallowed: any exception from ``llm_call``
    propagates to the caller so ``resolve()`` can fall back to required-only
    per D5 (design doc §5). No registry or storage logic here —
    ``eligible_defs`` is already resolved by the pipeline.
    """
    llm_call, model, provider = llm_target
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


class ToolSelectionPipeline:
    """Orchestrator that wires the stage helpers into a single ``resolve()``.

    Design doc §3 / §5.5: ``resolve()`` runs
    allowed → all_tools → eligible → required → validate → prompt_based →
    finalize → budget, and records every stage in ``meta``.

    Constructor dependencies (all duck-typed, all used only inside
    ``resolve()``):

    - ``registry`` — exposes ``tools() -> list[dict]`` (tool defs in
      registry order); the real ``HandlerRegistry`` or a fake.
    - ``storage`` — exposes ``get_or_create_context`` and/or
      ``get_context``; the real storage or a fake.
    - ``llm_adapter`` — exposes ``call_model(...)`` / ``get_text(...)``;
      only needed when the stage-6 LLM is actually consulted (the pipeline
      never resolves it when selection is disabled or below threshold).
    - ``config`` — a ``ConfigManager`` or plain dict: ``lazy_tool_loading.*``
      (``enabled``, ``min_eligible_to_select``) drive stage 6;
      ``max_handler_schema_tokens`` drives the stage-8 budget.
    """

    def __init__(self, registry, storage, llm_adapter, config):
        self.registry = registry
        self.storage = storage
        self.llm_adapter = llm_adapter
        self.config = config

    def resolve(
        self,
        agent,
        account_name: str,
        context_name: str,
        prompt_text: str,
    ) -> ToolSelection:
        """Run the full pipeline for one request and return the selection.

        Stages (design doc §3):

        1. ``allowed`` — ``agent.allowed_tools`` normalized (step 1).
        2. ``all_tools`` — every registered handler name, registry order.
        3. ``eligible`` — registry names ∩ allowed, registry order; unknown
           allowed names are ignored (design doc §3 step 3).
        4. ``required`` — the context's required tools, deduplicated.
        5. validate — ``ToolSelectionError(required_not_permissioned)`` when a
           required tool is not in ``allowed``; ``ToolSelectionError(
           required_not_registered)`` when it is not in the registry.
        6. ``prompt_based`` — the cheap LLM's minimal suggestion via
           ``query_llm``; skipped (no LLM call) when
           ``lazy_tool_loading.enabled`` is false or ``len(eligible) <
           min_eligible_to_select``. On any LLM failure the pipeline falls
           back to required-only and records ``meta['selection_error']`` (D5).
        7. ``active`` — ``required ∪ prompt_based``, dedup first-wins,
           resolved to full defs (``meta['active_defs']``). When selection
           was skipped the full eligible set stays active.
        8. budget — ``ToolSelectionError(budget_exceeded)`` when the active
           schemas exceed ``max_handler_schema_tokens``; a cap ≤ 0 disables
           the check; the pipeline never trims silently.
        """
        meta: Dict[str, Any] = {}

        # Step 1 — the agent's permissioned tools.
        allowed = get_agent_allowed_tools(agent)

        # Step 2 — every registered handler name, registry order.
        all_tools = (
            get_all_tools_from_registry(self.registry)
            if self.registry is not None
            else []
        )
        registry_names = set(all_tools)

        # Step 3 — eligible = registry names ∩ allowed (registry order;
        # unknown allowed names are ignored).
        allowed_set = set(allowed)
        eligible = [name for name in all_tools if name in allowed_set]

        # Step 4 — the context's required tools.
        required = get_required_tools(self.storage, account_name, context_name)

        # Step 5 — validate: required tools must be permissioned + registered.
        _validate_required(required, allowed_set, registry_names)

        # Step 6 — prompt-based selection via the cheap LLM.
        prompt_based, selection_meta = self._select_prompt_based(
            prompt_text, agent, eligible
        )
        meta["selection"] = selection_meta
        if selection_meta.get("error"):
            meta["selection_error"] = selection_meta["error"]

        # Step 7 — finalize: required ∪ prompt_based, dedup first-wins,
        # resolved to full defs. When selection was skipped (disabled /
        # below threshold) the full eligible set stays active — no selection
        # happened. On LLM failure the fallback is required-only (D5), which
        # falls out of ``required ∪ []``.
        if selection_meta.get("skipped"):
            active = list(eligible)
        else:
            active = _order_preserving_dedupe(required + prompt_based)
        active_defs = self._defs_by_name(active)
        meta["active_defs"] = active_defs

        # Step 8 — schema budget: raise when over the cap, never trim.
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

    def _select_prompt_based(
        self, prompt_text: str, agent, eligible: List[str]
    ) -> Tuple[List[str], Dict[str, Any]]:
        """Stage 6: ask the cheap LLM for the minimal active subset.

        Returns ``(prompt_based_names, selection_meta)``. The LLM is never
        called when ``lazy_tool_loading.enabled`` is false or when there are
        fewer eligible tools than ``lazy_tool_loading.min_eligible_to_select``
        (design doc D6) — those cases return ``([], {"skipped": True, ...})``
        and ``resolve()`` keeps the full eligible set active. Any failure in
        the selection-LLM path (``resolve_llm_target`` or ``query_llm``)
        falls back to required-only per D5:
        ``([], {"skipped": False, "error": ...})``.
        """
        ltl_cfg = _config_section(self.config, "lazy_tool_loading")
        enabled = bool(ltl_cfg.get("enabled", False))
        if not enabled:
            return [], {"skipped": True, "reason": "disabled"}

        min_eligible = _as_int(ltl_cfg.get("min_eligible_to_select"), 5)
        if len(eligible) < min_eligible:
            return [], {
                "skipped": True,
                "reason": "below_threshold",
                "min_eligible_to_select": min_eligible,
                "eligible_count": len(eligible),
            }

        eligible_defs = self._defs_by_name(eligible)
        try:
            llm_target = resolve_llm_target(self.config, agent, self.llm_adapter)
            prompt_based = query_llm(
                prompt_text,
                eligible_defs,
                llm_target=llm_target,
                config=self.config,
            )
        except Exception as exc:  # D5: fall back to required-only, never crash
            logging.warning(
                "tool_selection: prompt-based selection failed; "
                "falling back to required-only: %s",
                exc,
            )
            return [], {"skipped": False, "error": f"{type(exc).__name__}: {exc}"}

        _llm_call, model, provider = llm_target
        return prompt_based, {
            "skipped": False,
            "model": model,
            "provider": provider,
            "prompt_style": _resolve_prompt_style(self.config),
            "eligible_count": len(eligible),
            "suggested": prompt_based,
        }

    def _defs_by_name(self, names: List[str]) -> List[Dict[str, Any]]:
        """Resolve tool names to their full defs, ``names`` order preserved.

        Builds a name → def map from ``registry.tools()`` (so the resolved
        defs are exactly what the main model would receive) and skips names
        with no def. Registry order is preserved because ``names`` already
        carries the pipeline's deterministic order.
        """
        if self.registry is None:
            return []
        by_name = {
            td.get("name"): td
            for td in self.registry.tools()
            if td.get("name")
        }
        return [by_name[name] for name in names if name in by_name]


def _resolve_prompt_style(config) -> str:
    """Resolve the stage-6 prompt style from config, default ``'verb_first'``.

    Precedence: ``tool_selection.prompt_style`` >
    ``lazy_tool_loading.prompt_style`` (back-compat with the FCP's existing
    ``lazy_tool_loading`` config) > ``'verb_first'`` (selection.py default).
    Blank/whitespace-only values fall through.
    """
    ts_cfg = _config_section(config, "tool_selection")
    ltl_cfg = _config_section(config, "lazy_tool_loading")
    return _first_non_empty(
        ts_cfg.get("prompt_style"),
        ltl_cfg.get("prompt_style"),
    ) or "verb_first"


def _validate_required(
    required: List[str],
    allowed_set: set,
    registry_names_set: set,
) -> None:
    """Stage 5: raise when a required tool is not permissioned/registered.

    - ``required_not_permissioned`` — a required tool is missing from the
      agent's ``allowed_tools`` (permission, design doc §4).
    - ``required_not_registered`` — a required tool is unknown to the
      registry (no handler is registered under that name).

    The permissioned check runs first, so a tool that is both unknown and
    unpermissioned reports the permission problem. Empty ``required`` passes
    silently.
    """
    if not required:
        return
    missing_permission = [name for name in required if name not in allowed_set]
    if missing_permission:
        raise ToolSelectionError("required_not_permissioned", missing_permission)
    missing_registered = [name for name in required if name not in registry_names_set]
    if missing_registered:
        raise ToolSelectionError("required_not_registered", missing_registered)


def _schema_tokens(function_defs: List[Dict[str, Any]]) -> int:
    """Estimate schema tokens for tool defs (same heuristic as the FCP).

    ``json.dumps`` the defs and apply the prompt builder's
    ``estimate_tokens_from_text`` (``max(1, len(text) // 4)``). Kept local so
    the module stays dependency-free; parity with the FCP's
    ``_handler_schema_tokens``.
    """
    if not function_defs:
        return 0
    try:
        text = json.dumps(function_defs, ensure_ascii=False)
    except Exception:
        return 0
    return max(1, len(text) // 4)


def _resolve_schema_cap(config) -> Optional[int]:
    """Resolve the effective ``max_handler_schema_tokens`` cap.

    Mirrors the FCP's ``resolve_handler_schema_cap`` (design doc §5.5):

    - ``config['max_handler_schema_tokens'] > 0`` → that value.
    - ``<= 0`` → ``None`` (guardrail explicitly disabled).
    - missing / invalid / no config → ``DEFAULT_MAX_HANDLER_SCHEMA_TOKENS``.

    A ``None`` cap disables the stage-8 budget check entirely.
    """
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
    """Coerce ``value`` to int, falling back to ``default`` on junk/None."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _first_non_empty(*values: Any) -> Optional[str]:
    """Return the first non-blank string among ``values`` (else ``None``).

    ``None`` and whitespace-only values are skipped, so a blank config value
    falls through to the next precedence level instead of being "set".
    """
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _config_section(config, key: str) -> Dict[str, Any]:
    """Return ``config[key]`` as a dict, tolerating None / ConfigManager / junk.

    Accepts either a ``ConfigManager`` (``.get(key)`` returns the top-level
    value) or a plain dict. Non-dict values (missing section, ``None``,
    string, ...) yield ``{}`` so callers can use ``.get(...)`` safely.
    """
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
    """Infer a provider name from a model name (mirrors ProviderRegistry).

    Used by ``llm_source='direct'`` to pin a backend when no provider is
    configured. Prefixes are checked in order (deepseek, mistral, ollama,
    then openai-style gpt/o1/o3); unknown models default to ``'openai'``.
    """
    name = (model or "").strip().lower()
    for prefix, provider in _PROVIDER_PREFIXES:
        if name.startswith(prefix):
            return provider
    return "openai"


def _load_context(storage, account_name: str, context_name: str) -> Optional[Any]:
    """Load the active Context for account/context, or ``None`` (fail-soft).

    Mirrors the prompt builder's fallback (design doc §5.3): prefer
    ``get_or_create_context``, else ``get_context``, else ``None``. An empty
    or ``"none"`` context name means no context (same sentinel the FCP's
    ``load_context_state`` uses). Any storage error yields ``None`` so a
    broken context can never crash the pipeline.
    """
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
            logging.warning(
                "tool_selection: get_or_create_context(%r, %r) failed; "
                "falling back to get_context",
                account_name,
                context_name,
            )

    get_ctx = getattr(storage, "get_context", None)
    if callable(get_ctx):
        try:
            return get_ctx(account_name, context_name)
        except Exception:
            logging.warning(
                "tool_selection: get_context(%r, %r) failed; no required tools",
                account_name,
                context_name,
            )
            return None
    return None


def _order_preserving_dedupe(items: List[str]) -> List[str]:
    """Dedupe a list of strings, preserving first-occurrence order."""
    seen = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
