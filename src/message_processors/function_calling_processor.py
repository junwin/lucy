from dataclasses import dataclass
try:
    from injector import inject
except Exception:
    # Minimal shim for environments without the "injector" package (tests run in minimal environments).
    # The shim simply returns the function unchanged so the decorator has no effect.
    def inject(func):
        return func
import logging
from typing import Optional, Dict, Any, List, Iterable, Generator, Tuple
import json
import re
import time

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.message_processors.sse_events import SSEEvent
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.handlers.handler_registry import HandlerRegistry, filter_eligible_tool_defs
from src.agent import Agent
from src.agent.agent_manager import AgentManager

from src.llm.adapter_interface import LLMAdapter
from src.llm.provider_registry import ProviderRegistry

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent

from src.message_processors.automation_processor import AutomationProcessor
from src.message_processors.lazy_tool_selection import select_active_tool_defs
from src.tasklists.task import Task
from src.tasklists.task_list import TaskList

# Import token estimator from prompt_builder
from src.prompt_builders.prompt_builder import estimate_tokens_from_text


class ToolResultTooLargeError(Exception):
    """Raised when a tool result exceeds the configured max_tool_result_chars."""


class ToolHandlerError(Exception):
    """Raised when a tool handler fails during execution."""


# Default cap for the handler-schema token guardrail (overridable via the config
# key 'max_handler_schema_tokens').
DEFAULT_MAX_HANDLER_SCHEMA_TOKENS = 8000


@dataclass(frozen=True)
class _ProcessorContext:
    account_id: str
    agent_name: str
    conversation_id: str
    context_name: str
    model: str
    temperature: float
    context_type: str
    max_iterations: int
    store_this_call: bool
    delegation_depth: int
    provider: Optional[str] = None


@dataclass(frozen=True)
class _ToolCall:
    name: str
    call_id: str
    arguments_raw: str


def _log_token_breakdown(ctx: _ProcessorContext, prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> None:
    """Measure and log token counts for all prompt sections including handler definitions.

    Guarded against Mock objects in tests: if prompt_builder doesn't have a real
    breakdown dict, logs zeros across the board.
    """
    try:
        handlers_text = json.dumps(filtered_function_defs, ensure_ascii=False)
        handler_tokens = estimate_tokens_from_text(handlers_text)
    except Exception:
        handler_tokens = 0

    pb_breakdown = getattr(prompt_builder, "_last_prompt_token_breakdown", {})
    if isinstance(pb_breakdown, dict):
        system_tokens = pb_breakdown.get("system_session", 0)
        context_tokens = pb_breakdown.get("context_text", 0)
        obsidian_tokens = pb_breakdown.get("obsidian_notes", 0)
        digest_tokens = pb_breakdown.get("digest_embeddings", 0)
        history_tokens = pb_breakdown.get("chat_history", 0)
        user_tokens = pb_breakdown.get("current_user_message", 0)
        total_without_handlers = pb_breakdown.get("total_without_handlers", 0)
    else:
        # Mock or other non-dict — safe zeroes
        system_tokens = context_tokens = obsidian_tokens = digest_tokens = history_tokens = user_tokens = total_without_handlers = 0

    total_tokens = total_without_handlers + handler_tokens

    logging.info(
        "Prompt.token_breakdown: agent=%s account=%s session=%s system=%d handlers=%d context=%d obsidian=%d digest=%d history=%d user=%d total=%d",
        ctx.agent_name,
        ctx.account_id,
        ctx.conversation_id,
        system_tokens,
        handler_tokens,
        context_tokens,
        obsidian_tokens,
        digest_tokens,
        history_tokens,
        user_tokens,
        total_tokens,
    )


def load_context_state(prompt_builder: Any, account_name: str, context_name: str) -> Optional[Any]:
    """Load the active Context (or None) for the given account/context.

    Delegates to PromptBuilder._get_context_state when available so the FCP
    sees exactly the same Context the prompt builder used (same
    get_or_create_context/get_context fallback). Fails softly: any error
    yields None (no context tool list applies).
    """
    if not context_name or context_name == "none":
        return None
    try:
        loader = getattr(prompt_builder, "_get_context_state", None)
        if callable(loader):
            return loader(account_name, context_name)
        storage = getattr(prompt_builder, "storage", None)
        if storage is None:
            return None
        if hasattr(storage, "get_or_create_context"):
            return storage.get_or_create_context(account_name, context_name)
        return storage.get_context(account_name, context_name)
    except Exception as ex:
        logging.warning(
            "FunctionCallingProcessor: failed to load context '%s' for account '%s': %s",
            context_name,
            account_name,
            ex,
        )
        return None


def resolve_tool_defs(registry, agent, context_state: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Resolve the tool definitions the agent is allowed to use.

    Thin wrapper over the shared filter_eligible_tool_defs() helper (the
    same one HandlerRegistry.eligible_tool_defs uses). Kept for backward
    compatibility with existing callers.

    Single source of truth for tool-list resolution across
    process_message(), process_message_streaming(), and the
    /prompt_builder/metrics endpoint.

    See filter_eligible_tool_defs() for the full filtering rules.
    """
    function_defs = registry.tools() if registry is not None else []
    return filter_eligible_tool_defs(function_defs, agent, context_state)



def _handler_schema_tokens(function_defs: List[Dict[str, Any]]) -> int:
    """Estimate schema tokens for a list of tool defs (same estimator as the prompt builder)."""
    if not function_defs:
        return 0
    try:
        text = json.dumps(function_defs, ensure_ascii=False)
    except Exception:
        return 0
    return estimate_tokens_from_text(text)


def resolve_handler_schema_cap(config: Any) -> Optional[int]:
    """Resolve the effective max_handler_schema_tokens cap from config.

    Returns None when the guardrail is disabled. Resolution order:
      1. config['max_handler_schema_tokens'] > 0  -> that value
      2. config['max_handler_schema_tokens'] <= 0 -> None (explicitly disabled)
      3. key missing / invalid / no config         -> DEFAULT_MAX_HANDLER_SCHEMA_TOKENS
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
            logging.warning(
                "FunctionCallingProcessor: invalid max_handler_schema_tokens=%r; using default %d",
                raw,
                DEFAULT_MAX_HANDLER_SCHEMA_TOKENS,
            )
    return DEFAULT_MAX_HANDLER_SCHEMA_TOKENS


def apply_handler_schema_budget(
    function_defs: List[Dict[str, Any]],
    config: Any,
    *,
    agent_name: str = "<unknown>",
) -> List[Dict[str, Any]]:
    """Trim tool defs from the tail when schema tokens exceed the configured cap.

    Pure guardrail - never a selection mechanism. Runs AFTER resolution
    (resolve_tool_defs), so it can only remove tools, never add or reorder.

    - Under/at the cap: returns the list unchanged, no log.
    - Over the cap: removes tool defs from the tail until under the cap,
      always keeping at least one def (a single oversized def is kept; trimming
      to zero tools would disable tool use entirely, which is a policy decision
      for allowed_tools, not a token guardrail). Logs a warning with the
      before/after token counts and how many defs were trimmed.
    """
    if not function_defs:
        return function_defs

    cap = resolve_handler_schema_cap(config)
    if cap is None:
        return function_defs

    trimmed = list(function_defs)
    tokens = _handler_schema_tokens(trimmed)
    if tokens <= cap:
        return trimmed

    original_count = len(trimmed)
    original_tokens = tokens
    while len(trimmed) > 1 and tokens > cap:
        trimmed.pop()
        tokens = _handler_schema_tokens(trimmed)

    logging.warning(
        "FunctionCallingProcessor: handler schema tokens=%d exceed cap=%d for agent '%s'; "
        "trimmed %d tool def(s) from the tail (kept %d, tokens=%d)",
        original_tokens,
        cap,
        agent_name,
        original_count - len(trimmed),
        len(trimmed),
        tokens,
    )
    return trimmed


def merge_mandatory_tools(
    function_defs: List[Dict[str, Any]],
    context_state: Optional[Any],
    registry: Any,
    agent: Any,
) -> List[Dict[str, Any]]:
    """Merge a context's required tools into the active tool defs.

    The ONLY supported interface for external consumers is the Context's
    aggregated `required_tools` (own `mandatory_tools` + each resolved skill's
    `mandatory_tools`). This guarantees those tools are always present in the
    schema sent to the LLM, even when the user's request does not obviously
    need them. There is no fallback to the raw `mandatory_tools` list or
    legacy data/extra dicts.

    Rules (mirrors filter_eligible_tool_defs conventions):
    - Missing / non-list / empty `required_tools` => no-op.
    - Names are resolved against the FULL registry, not the already-filtered
      list, so a required tool survives lazy tool selection that dropped it.
    - agent.allowed_tools remains the hard ceiling: a required tool outside
      it is logged and skipped.
    - Dedup: names already present in function_defs and repeated names inside
      the required list are skipped.
    - Unknown names are logged and ignored.
    - No config controls: the feature is active whenever a context provides
      `required_tools`.

    Required defs are inserted at the FRONT of the list so the
    apply_handler_schema_budget() tail-trim can never strip them.
    """
    if context_state is None:
        return function_defs

    # required_tools is the ONLY supported interface for external consumers.
    # It is the Context.required_tools property: the aggregate of the context's
    # own mandatory_tools PLUS each resolved skill's mandatory_tools.
    raw = getattr(context_state, "required_tools", None)
    if raw is None:
        return function_defs
    if isinstance(raw, (str, bytes)):
        logging.warning(
            "FunctionCallingProcessor: context 'mandatory_tools' must be a list; ignoring",
        )
        return function_defs
    try:
        names = list(raw)
    except Exception:
        logging.warning(
            "FunctionCallingProcessor: context 'mandatory_tools' is not iterable; ignoring",
        )
        return function_defs
    if not names:
        return function_defs

    # agent.allowed_tools is the hard ceiling (same convention as
    # filter_eligible_tool_defs).
    allowed = getattr(agent, "allowed_tools", None)
    if not allowed:
        logging.warning(
            "FunctionCallingProcessor: context declares mandatory_tools=%s but agent '%s' "
            "has no allowed_tools; skipping all",
            names,
            getattr(agent, "name", "<unknown>"),
        )
        return function_defs
    try:
        allowed_set = set(list(allowed))
    except Exception:
        allowed_set = set()

    # Resolve against the full registry so mandatory tools survive lazy
    # selection (which may have dropped them from function_defs).
    all_defs = registry.tools() if registry is not None else []
    def_by_name = {fd.get("name"): fd for fd in all_defs if fd.get("name")}

    existing_names = {fd.get("name") for fd in function_defs if fd.get("name")}
    mandatory_defs: List[Dict[str, Any]] = []
    seen = set(existing_names)
    for name in names:
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name in seen:
            continue
        seen.add(name)
        if name not in allowed_set:
            logging.warning(
                "FunctionCallingProcessor: mandatory tool '%s' not in agent '%s' "
                "allowed_tools; skipping",
                name,
                getattr(agent, "name", "<unknown>"),
            )
            continue
        fd = def_by_name.get(name)
        if fd is None:
            logging.warning(
                "FunctionCallingProcessor: mandatory tool '%s' unknown to registry; ignoring",
                name,
            )
            continue
        mandatory_defs.append(fd)

    if not mandatory_defs:
        return function_defs

    logging.info(
        "FunctionCallingProcessor: merged %d mandatory tool def(s) from context: %s",
        len(mandatory_defs),
        [d.get("name") for d in mandatory_defs],
    )

    # Front-insert so the handler-schema budget tail-trim cannot strip them.
    return mandatory_defs + list(function_defs)


class FunctionCallingProcessor(MessageProcessorInterface):
    @inject
    def __init__(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: LLMAdapter,
        chat2_store: Optional[Chat2Store] = None,
        automation_processor: Optional[AutomationProcessor] = None,
        agent_manager: Optional[AgentManager] = None,
    ):
        self.config = config
        self.registry = registry
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter
        self.chat2_store = chat2_store
        self.automation_processor = automation_processor
        self.agent_manager = agent_manager

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _safe_json_loads(self, s: str) -> Dict[str, Any]:
        if not s:
            return {}
        try:
            loaded = json.loads(s)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            logging.warning(
                "Tool arguments were not valid JSON; using empty dict. args=%r",
                (s or "")[:500],
            )
            return {}

    def _tool_result_to_text(self, tool_result_text: Any) -> str:
        """Ensure the tool result is a string and enforce max size.

        We do not parse/serialize tool I/O here anymore. Handlers are expected
        to return a JSON object string.
        """

        if tool_result_text is None:
            s = json.dumps({"ok": False, "error": "Tool returned None"}, ensure_ascii=False)
        elif isinstance(tool_result_text, str):
            s = tool_result_text
        else:
            try:
                s = json.dumps(tool_result_text, ensure_ascii=False)
            except Exception as e:
                s = json.dumps({"ok": False, "error": f"Tool result not serializable: {e}"}, ensure_ascii=False)

        max_chars = int(self.config.get("max_tool_result_chars", 20000))
        if len(s) > max_chars:
            logging.error(
                "Tool result too large: %d chars (limit %d). Sample: %r",
                len(s),
                max_chars,
                s[:1000],
            )
            raise ToolResultTooLargeError(f"Tool result too large: {len(s)} chars (limit {max_chars})")

        return s

    def _build_context(
        self,
        *,
        primary_agent: Agent,
        account: Dict[str, Any],
        conversation_id: str,
        context_name: str,
    ) -> _ProcessorContext:
        account_id = (account.get("accountId") or "").strip()
        agent_name = primary_agent.name or "unknown"

        max_iterations = int(primary_agent.max_function_call_iterations or 10)
        if max_iterations <= 0:
            logging.warning(
                "max_function_call_iterations for agent '%s' is %d; using 1 instead",
                agent_name,
                max_iterations,
            )
            max_iterations = 1

        # Resolve provider name if agent has explicit provider; otherwise None.
        provider_explicit = getattr(primary_agent, "provider", None)
        if provider_explicit:
            try:
                provider = ProviderRegistry.resolve_name(primary_agent.model, provider_explicit)
            except ValueError:
                logging.warning(
                    "FCP: unknown provider '%s' for agent '%s', ignoring",
                    provider_explicit,
                    agent_name,
                )
                provider = None
        else:
            provider = None

        return _ProcessorContext(
            account_id=account_id,
            agent_name=agent_name,
            conversation_id=conversation_id,
            context_name=context_name,
            model=primary_agent.model,
            temperature=primary_agent.temperature,
            context_type=primary_agent.context_type or "hybrid",
            max_iterations=max_iterations,
            store_this_call=bool(primary_agent.save_responses),
            delegation_depth=int(getattr(primary_agent, "delegation_depth", 0)),
            provider=provider,
        )

    def _wrap_tool_calls(self, tool_calls: Iterable[Dict[str, Any]]) -> List[_ToolCall]:
        wrapped: List[_ToolCall] = []
        for tc in tool_calls or []:
            tool_name = tc.get("name") or ""
            tool_call_id = tc.get("id")
            args_raw = tc.get("arguments") or "{}"
            wrapped.append(_ToolCall(name=tool_name, call_id=str(tool_call_id or ""), arguments_raw=args_raw))
        return wrapped

    def _get_environment_system_messages(self) -> List[str]:
        """Return server-wide environment prompt injection messages.

        Config key: environment_prompt_block

        - Missing/empty => []
        - Non-empty string => one system message containing the full block
        """

        env_block = self.config.get("environment_prompt_block", "")
        if not isinstance(env_block, str) or not env_block.strip():
            return []

        # Keep as a single structured block to preserve formatting.
        return [env_block.strip()]

    def _resolve_active_function_defs(
        self,
        *,
        message: str,
        filtered_function_defs: List[Dict[str, Any]],
        ctx: _ProcessorContext,
        metrics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Optionally reduce the eligible tool defs to the minimal active subset.

        Lazy tool loading: instead of sending every eligible schema to the main
        model, ask a cheap LLM to pick the tools the request is likely to need,
        then apply deterministic expansion rules. This is a pure optimization --
        on any failure (or when disabled) the full eligible set is returned so
        the request still works.
        """
        cfg = self.config.get("lazy_tool_loading") or {}
        if not isinstance(cfg, dict) or not bool(cfg.get("enabled", False)):
            return filtered_function_defs

        exclude = {n for n in (cfg.get("exclude_tools") or []) if n}
        eligible = [
            d for d in filtered_function_defs
            if (d.get("name") or "") not in exclude
        ]
        if not eligible:
            return filtered_function_defs

        model = (cfg.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
        provider = (cfg.get("provider") or "").strip() or None
        prompt_style = (cfg.get("prompt_style") or "verb_first").strip() or "verb_first"

        def _llm_call(messages: List[Dict[str, str]]) -> str:
            response = self.llm_adapter.call_model(
                model=model,
                input=messages,
                temperature=0.0,
                provider=provider,
            )
            return self.llm_adapter.get_text(response) or ""

        try:
            active, meta = select_active_tool_defs(
                prompt_text=message,
                eligible_defs=eligible,
                llm_call=_llm_call,
                prompt_style=prompt_style,
                three_sisters=bool(cfg.get("three_sisters", True)),
                tasklist_pair=bool(cfg.get("tasklist_pair", True)),
                rules=bool(cfg.get("rules", True)),
                min_eligible_to_select=int(cfg.get("min_eligible_to_select", 5)),
                allow_empty_active_set=bool(cfg.get("allow_empty_active_set", False)),
            )
        except Exception:
            logging.exception(
                "FunctionCallingProcessor: lazy tool selection failed agent=%s session_id=%s; "
                "falling back to full eligible set",
                ctx.agent_name,
                ctx.conversation_id,
            )
            metrics["lazy_tool_selection_error"] = True
            return eligible

        metrics["lazy_tool_selection"] = meta

        tokens = meta.get("tokens") or {}
        if meta.get("skipped"):
            logging.info(
                "FunctionCallingProcessor: lazy tool selection skipped agent=%s reason=%s eligible=%d",
                ctx.agent_name,
                meta.get("reason"),
                meta.get("eligible_count", 0),
            )
        else:
            logging.info(
                "FunctionCallingProcessor: lazy tool selection agent=%s session_id=%s eligible=%d active=%d "
                "savings_tokens=%s net_savings_tokens=%s rules_hits=%s",
                ctx.agent_name,
                ctx.conversation_id,
                meta.get("eligible_count", 0),
                meta.get("active_count", 0),
                tokens.get("savings_tokens", 0),
                tokens.get("net_savings_tokens", 0),
                meta.get("rules_hits"),
            )

        return active



    def _execute_tool_calls(
        self,
        *,
        tool_calls: List[_ToolCall],
        primary_agent: Agent,
        secondary_agent: Optional[Agent],
        processor_factory: Optional[Any],
        account: Dict[str, Any],
        ctx: _ProcessorContext,
        metrics: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[_ToolCall, str]]]:
        tool_output_items: List[Dict[str, Any]] = []
        raw_results: List[Tuple[_ToolCall, str]] = []

        # Build the shared execution context for handlers that need it
        # (e.g. TasklistsRunHandler needs primary_agent, account, conversation_id, etc.)
        # NOTE: account_name is NOT included here — it's passed explicitly to execute().
        handler_context: Dict[str, Any] = {
            "primary_agent": primary_agent,
            "secondary_agent": secondary_agent,
            "secondary_agent_default_context": getattr(secondary_agent, "default_context", None),
            "processor_factory": processor_factory,
            "account": account,
            "conversation_id": ctx.conversation_id,
            "context_name": ctx.context_name,
            "context_state": load_context_state(self.prompt_builder, ctx.account_id, ctx.context_name),
            "agent_name": ctx.agent_name,
            "storage": getattr(self, "_storage", None),
            "registry": self.registry,
            "prompt_builder": self.prompt_builder,
            "config": self.config,
            "chat2_store": self.chat2_store,
            "llm_adapter": self.llm_adapter,
            "agent_manager": self.agent_manager,
        }

        for tc in tool_calls:
            metrics["tool_calls"] += 1

            if not tc.call_id:
                metrics["failures"] += 1
                raise ToolHandlerError(
                    f"Tool call missing id/call_id for tool '{tc.name}'. Cannot send function_call_output."
                )

            # Unknown tool name: the model asked for a tool we don't have
            # (e.g. 'bash'). Return a recoverable error to the LLM instead of
            # crashing the whole request, so the model can correct itself on
            # the next turn.
            has_tool = getattr(self.registry, "has_tool", None)
            if callable(has_tool) and not has_tool(tc.name):
                metrics["failures"] += 1
                valid = getattr(self.registry, "tool_names", lambda: [])()
                logging.error(
                    "Unknown tool requested by model: tool=%r call_id=%s args=%r valid_tools=%s",
                    tc.name,
                    tc.call_id,
                    tc.arguments_raw,
                    valid,
                )
                tool_result_text = json.dumps(
                    {
                        "ok": False,
                        "tool": tc.name,
                        "error": f"Unknown tool '{tc.name}'. Valid tools: {valid}",
                    },
                    ensure_ascii=False,
                )
                raw_results.append((tc, tool_result_text))
                tool_output_items.append(
                    self.llm_adapter.format_tool_output(
                        call_id=str(tc.call_id), output=tool_result_text
                    )
                )
                continue

            try:
                handler = self.registry.create(tc.name, config=self.config)

                logging.info(
                    "tool_execute_start tool=%s call_id=%s account=%s",
                    tc.name,
                    tc.call_id,
                    ctx.account_id,
                )

                if hasattr(handler, "execute_raw"):
                    tool_result_text = handler.execute_raw(tc.arguments_raw, account_name=ctx.account_id, call_id=tc.call_id, **handler_context)  # type: ignore[attr-defined]
                else:
                    tool_args = self._safe_json_loads(tc.arguments_raw)
                    tool_result = handler.execute(tool_args, account_name=ctx.account_id, **handler_context)
                    tool_result_text = json.dumps(tool_result, ensure_ascii=False)

                logging.info(
                    "tool_execute_done tool=%s call_id=%s result_preview=%r",
                    tc.name,
                    tc.call_id,
                    (tool_result_text or "")[:200],
                )

                if tc.name == "delegate_tasks" and secondary_agent is not None and processor_factory is not None and self.automation_processor is not None:
                    try:
                        maybe = json.loads(tool_result_text or "{}")
                    except Exception:
                        maybe = {}

                    if isinstance(maybe, dict) and maybe.get("ok") and maybe.get("kind") == "tasklist":
                        logging.info(
                            "FunctionCallingProcessor: delegating tasklist to AutomationProcessor supervisor=%s worker=%s session_id=%s call_id=%s",
                            ctx.agent_name,
                            secondary_agent.name,
                            ctx.conversation_id,
                            tc.call_id,
                        )
                        try:
                            # Build TaskList from delegate_tasks result
                            tasklist_id = f"auto-{ctx.conversation_id}"
                            description = maybe.get("description") or ""
                            tasks = maybe.get("tasks") or []

                            task_objects = []
                            for t in tasks:
                                t_id = t.get("id") or f"task-{len(task_objects)+1}"
                                t_name = t.get("title") or ""
                                t_instruction = t.get("instruction") or ""
                                t_meta = {}
                                if t.get("file"):
                                    t_meta["file"] = t["file"]
                                if t.get("params"):
                                    t_meta.update(t["params"])
                                task_objects.append(Task(
                                    id=t_id,
                                    name=t_name,
                                    instructions=t_instruction,
                                    meta=t_meta,
                                ))

                            tasklist = TaskList(
                                id=tasklist_id,
                                name=description[:80] or "auto-tasklist",
                                description=description,
                                tasks=task_objects,
                            )

                            # Persist to storage via AutomationProcessor storage
                            self.automation_processor.storage.save_tasklist(
                                ctx.account_id, tasklist_id, tasklist.to_dict()
                            )

                            # Execute via AutomationProcessor
                            result_text = self.automation_processor.execute_tasklist(
                                tasklist_id=tasklist_id,
                                mode="multi-step",
                                account_name=ctx.account_id,
                                agent_name=ctx.agent_name,
                                conversation_id=ctx.conversation_id,
                                context_name=ctx.context_name,
                                primary_agent=primary_agent,
                                account=account,
                                secondary_agent=secondary_agent,
                                processor_factory=processor_factory,
                            )

                            tool_result_text = json.dumps({
                                "ok": True,
                                "tasklist_id": tasklist_id,
                                "result": result_text,
                            }, ensure_ascii=False)

                        except Exception as e:
                            logging.exception(
                                "FunctionCallingProcessor: AutomationProcessor delegation failed supervisor=%s session_id=%s",
                                ctx.agent_name,
                                ctx.conversation_id,
                            )
                            tool_result_text = json.dumps({
                                "ok": False,
                                "error": f"Tasklist delegation failed: {type(e).__name__}: {e}",
                            }, ensure_ascii=False)

                # Collect raw result before enforcing max size (for SSE action/image inspection)
                raw_results.append((tc, tool_result_text))

                tool_result_text = self._tool_result_to_text(tool_result_text)

            except ToolResultTooLargeError as e:
                metrics["failures"] += 1
                # Replace the too-large raw result with a compact error so the
                # LLM sees a graceful tool-failure message instead of a hard crash.
                error_msg = str(e)
                if tc.name == "serve_image":
                    # Parse char count and limit from the error string to craft
                    # a helpful message that tells the LLM exactly what to do.
                    m = re.match(r"Tool result too large: (\d+) chars \(limit (\d+)\)", error_msg)
                    if m:
                        error_msg = (
                            f"Image too large for tool result ({m.group(1)} chars, limit {m.group(2)}). "
                            "Please retry with max_dimension=512 or smaller."
                        )
                    else:
                        error_msg += " Please retry with max_dimension=512 or smaller."
                error_dict = {"ok": False, "tool": tc.name, "error": error_msg}
                tool_result_text = json.dumps(error_dict, ensure_ascii=False)
                raw_results.pop()  # remove the too-large entry
                raw_results.append((tc, tool_result_text))
                # Fall through to tool_output_items.append below.
            except Exception as e:
                metrics["failures"] += 1
                logging.exception("Tool execution failed: %s call_id=%s", tc.name, tc.call_id)
                raise ToolHandlerError(f"{type(e).__name__}: {e}")

            tool_output_items.append(self.llm_adapter.format_tool_output(call_id=str(tc.call_id), output=tool_result_text))

        return tool_output_items, raw_results



    def _tool_calls_are_duplicate(
        self,
        current: List[_ToolCall],
        previous: List[_ToolCall],
    ) -> bool:
        """Return True if current tool calls are identical to previous (same names + same arguments)."""
        if not previous or not current:
            return False
        if len(current) != len(previous):
            return False
        for c, p in zip(current, previous):
            if c.name != p.name or c.arguments_raw != p.arguments_raw:
                return False
        return True


    def _run_llm_loop(
        self,
        *,
        ctx: _ProcessorContext,
        prompt_messages: List[Dict[str, Any]],
        function_defs: List[Dict[str, Any]],
        primary_agent: Agent,
        secondary_agent: Optional[Agent],
        processor_factory: Optional[Any],
        account: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> str:
        response_text = ""
        previous_response_id: Optional[str] = None
        previous_tool_calls: Optional[List[_ToolCall]] = None

        next_input_items: List[Dict[str, Any]] = prompt_messages

        for iteration in range(1, ctx.max_iterations + 1):
            metrics["iterations"] = iteration
            metrics["openai_calls"] += 1

            # --- Call model with empty-response retry ---
            MAX_EMPTY_RETRIES = 2
            llm_response = None
            tool_calls: List[_ToolCall] = []

            for retry_attempt in range(MAX_EMPTY_RETRIES + 1):
                if retry_attempt > 0:
                    metrics["openai_calls"] += 1
                    logging.warning(
                        "FCP: empty LLM response at iteration=%d, retry %d/%d agent=%s session_id=%s",
                        iteration, retry_attempt, MAX_EMPTY_RETRIES, ctx.agent_name, ctx.conversation_id,
                    )

                llm_response = self.llm_adapter.call_model(
                    model=ctx.model,
                    input=next_input_items,
                    temperature=ctx.temperature,
                    tools=function_defs,
                    tool_choice="auto" if function_defs else None,
                    store=ctx.store_this_call,
                    metadata={"conversation_id": ctx.conversation_id, "session_id": ctx.context_name or None},
                    previous_response_id=previous_response_id,
                    provider=ctx.provider,
                )

                logging.debug(
                    "FunctionCallingProcessor: raw LLM response agent=%s session_id=%s iteration=%d type=%s llm_response=%r",
                    ctx.agent_name,
                    ctx.conversation_id,
                    iteration,
                    type(llm_response).__name__,
                    llm_response,
                )

                result_response_id = self.llm_adapter.get_response_id(llm_response)
                if result_response_id:
                    previous_response_id = result_response_id

                tool_calls_raw = self.llm_adapter.extract_tool_calls(llm_response)
                tool_calls = self._wrap_tool_calls(tool_calls_raw)

                logging.info(
                    "FunctionCallingProcessor: raw tool calls agent=%s session_id=%s iteration=%d raw=%r wrapped=%r",
                    ctx.agent_name,
                    ctx.conversation_id,
                    iteration,
                    tool_calls_raw,
                    [(t.name, t.call_id, t.arguments_raw) for t in tool_calls],
                )

                if tool_calls or self.llm_adapter.get_text(llm_response):
                    break  # got a real response
            else:
                # All retries exhausted — use fallback
                response_text = "I received an empty response from the model — please try again."
                logging.error(
                    "FCP: empty LLM response after %d retries at iteration=%d agent=%s session_id=%s — using fallback",
                    MAX_EMPTY_RETRIES, iteration, ctx.agent_name, ctx.conversation_id,
                )
                break

            logging.info(
                "FunctionCallingProcessor: iteration=%d/%d agent=%s session_id=%s response_id=%s",
                iteration,
                ctx.max_iterations,
                ctx.agent_name,
                ctx.conversation_id,
                previous_response_id,
            )

            if tool_calls:
                # --- Duplicate tool call detection ---
                if self._tool_calls_are_duplicate(tool_calls, previous_tool_calls):
                    logging.warning(
                        "FunctionCallingProcessor: duplicate tool calls detected at iteration=%d/%d "
                        "agent=%s session_id=%s tool_count=%d. Breaking loop.",
                        iteration,
                        ctx.max_iterations,
                        ctx.agent_name,
                        ctx.conversation_id,
                        len(tool_calls),
                    )
                    response_text = (
                        "I noticed I was repeating the same tool call without making progress. "
                        "I've stopped to avoid getting stuck in a loop. "
                        "Please rephrase your request or be more specific about what you need."
                    )
                    break

                previous_tool_calls = tool_calls
                # --- End duplicate detection ---

                if not previous_response_id:
                    metrics["failures"] += 1
                    raise ToolHandlerError(
                        "LLM returned tool_calls but no response_id. "
                        "Cannot chain function_call_output. Ensure the LLMApi propagates response_id."
                    )

                logging.info(
                    "FunctionCallingProcessor: tool_call iteration=%d/%d agent=%s session_id=%s tool_count=%d prev_response_id=%s",
                    iteration,
                    ctx.max_iterations,
                    ctx.agent_name,
                    ctx.conversation_id,
                    len(tool_calls),
                    previous_response_id,
                )

                tool_output_items, _ = self._execute_tool_calls(
                    tool_calls=tool_calls,
                    primary_agent=primary_agent,
                    secondary_agent=secondary_agent,
                    processor_factory=processor_factory,
                    account=account,
                    ctx=ctx,
                    metrics=metrics,
                )

                logging.info(
                    "FunctionCallingProcessor: sending %d function_call_output items chained to response_id=%s call_ids=%s",
                    len(tool_output_items),
                    previous_response_id,
                    [x.get("call_id") for x in tool_output_items],
                )

                next_input_items = tool_output_items

                if iteration >= ctx.max_iterations:
                    metrics["failures"] += 1
                    logging.error(
                        "FunctionCallingProcessor: exceeded max_function_call_iterations=%d for agent '%s' in conversation_id=%s",
                        ctx.max_iterations,
                        ctx.agent_name,
                        ctx.conversation_id,
                    )
                    response_text = (
                        "I ran into an internal limit while trying to call tools multiple times. "
                        "I may not have completed all requested actions. Please try rephrasing or splitting your request."
                    )
                    break

                # ── Provider throttle: pause between tool-call iterations ──
                provider_name = ProviderRegistry.resolve_name(ctx.model, ctx.provider)
                throttle_ms = self.config.get("provider_throttle_ms", {}).get(provider_name, 0)
                if throttle_ms > 0:
                    time.sleep(throttle_ms / 1000.0)

                continue

            response_text = self.llm_adapter.get_text(llm_response)
            break

        logging.info(
            "FunctionCallingProcessor: completed agent=%s session_id=%s iterations=%d response_preview=%r",
            ctx.agent_name,
            ctx.conversation_id,
            iteration,
            (response_text or "")[:80],
        )

        return response_text

    # ------------------------------------------------------------------
    # Streaming loop (Phase 1 SSE)
    # ------------------------------------------------------------------

    @staticmethod
    def _inspect_raw_results(
        raw_results: List[Tuple[_ToolCall, str]],
    ) -> Generator[SSEEvent, None, None]:
        """Inspect raw tool results for image (PNG/SVG) and action keys.

        Yields SSEEvent objects for any detected keys.
        """
        for _tc, raw_text in raw_results:
            try:
                parsed = json.loads(raw_text) if isinstance(raw_text, str) else {}
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(parsed, dict):
                continue

            # Action events
            if "action" in parsed:
                yield SSEEvent(
                    type="action",
                    action=parsed["action"],
                    action_payload=parsed.get("action_payload"),
                )

            # SVG images — emit as event:image with format=svg
            if "svg" in parsed:
                svg = parsed["svg"]
                if isinstance(svg, dict):
                    yield SSEEvent(
                        type="image",
                        format="svg",
                        svg_markup=svg.get("markup"),
                        alt=svg.get("alt") or "",
                        width=svg.get("width"),
                        height=svg.get("height"),
                    )

            # PNG images (existing) — emit as event:image with image_url
            if "image" in parsed and "svg" not in parsed:
                img = parsed["image"]
                if isinstance(img, dict):
                    yield SSEEvent(
                        type="image",
                        format="png",
                        image_url=img.get("url"),
                        alt=img.get("alt"),
                    )

    def _run_llm_loop_streaming(
        self,
        *,
        ctx: _ProcessorContext,
        prompt_messages: List[Dict[str, Any]],
        function_defs: List[Dict[str, Any]],
        primary_agent: Agent,
        secondary_agent: Optional[Agent],
        processor_factory: Optional[Any],
        account: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Generator[SSEEvent, None, None]:
        """Mirrors _run_llm_loop but yields SSEEvent objects at key points.

        Injection points:
          A - tool_call  (before each tool executes)
          B - tool_result (after each tool completes)
          C - text        (final assistant text)
          D - done        (stream complete)
        """
        response_text = ""
        previous_response_id: Optional[str] = None
        previous_tool_calls: Optional[List[_ToolCall]] = None

        next_input_items: List[Dict[str, Any]] = prompt_messages

        for iteration in range(1, ctx.max_iterations + 1):
            metrics["iterations"] = iteration
            metrics["openai_calls"] += 1

            # --- Call model with empty-response retry ---
            MAX_EMPTY_RETRIES = 2
            llm_response = None
            tool_calls: List[_ToolCall] = []

            for retry_attempt in range(MAX_EMPTY_RETRIES + 1):
                if retry_attempt > 0:
                    metrics["openai_calls"] += 1
                    logging.warning(
                        "FCP: empty LLM response at iteration=%d, retry %d/%d agent=%s session_id=%s",
                        iteration, retry_attempt, MAX_EMPTY_RETRIES, ctx.agent_name, ctx.conversation_id,
                    )

                llm_response = self.llm_adapter.call_model(
                    model=ctx.model,
                    input=next_input_items,
                    temperature=ctx.temperature,
                    tools=function_defs,
                    tool_choice="auto" if function_defs else None,
                    store=ctx.store_this_call,
                    metadata={"conversation_id": ctx.conversation_id, "session_id": ctx.context_name or None},
                    previous_response_id=previous_response_id,
                    provider=ctx.provider,
                )

                logging.debug(
                    "FunctionCallingProcessor(streaming): raw LLM response agent=%s session_id=%s iteration=%d type=%s llm_response=%r",
                    ctx.agent_name,
                    ctx.conversation_id,
                    iteration,
                    type(llm_response).__name__,
                    llm_response,
                )

                result_response_id = self.llm_adapter.get_response_id(llm_response)
                if result_response_id:
                    previous_response_id = result_response_id

                tool_calls_raw = self.llm_adapter.extract_tool_calls(llm_response)
                tool_calls = self._wrap_tool_calls(tool_calls_raw)

                logging.info(
                    "FunctionCallingProcessor(streaming): raw tool calls agent=%s session_id=%s iteration=%d raw=%r wrapped=%r",
                    ctx.agent_name,
                    ctx.conversation_id,
                    iteration,
                    tool_calls_raw,
                    [(t.name, t.call_id, t.arguments_raw) for t in tool_calls],
                )

                if tool_calls or self.llm_adapter.get_text(llm_response):
                    break  # got a real response
            else:
                # All retries exhausted — use fallback
                response_text = "I received an empty response from the model — please try again."
                logging.error(
                    "FCP: empty LLM response after %d retries at iteration=%d agent=%s session_id=%s — using fallback",
                    MAX_EMPTY_RETRIES, iteration, ctx.agent_name, ctx.conversation_id,
                )
                break

            logging.info(
                "FunctionCallingProcessor(streaming): iteration=%d/%d agent=%s session_id=%s response_id=%s",
                iteration,
                ctx.max_iterations,
                ctx.agent_name,
                ctx.conversation_id,
                previous_response_id,
            )

            # ── Always extract and yield text BEFORE the tool_calls check ──
            # Providers like DeepSeek often return text + tool_calls in the same
            # response. We must surface the text to the frontend even when tool
            # calls are also present.
            response_text = self.llm_adapter.get_text(llm_response)
            if response_text:
                yield SSEEvent(
                    type="text",
                    content=response_text,
                    message_id=f"msg-{ctx.conversation_id}-iter-{iteration}",
                )

            if tool_calls:
                # --- Duplicate tool call detection ---
                if self._tool_calls_are_duplicate(tool_calls, previous_tool_calls):
                    logging.warning(
                        "FunctionCallingProcessor(streaming): duplicate tool calls detected at iteration=%d/%d "
                        "agent=%s session_id=%s tool_count=%d. Breaking loop.",
                        iteration,
                        ctx.max_iterations,
                        ctx.agent_name,
                        ctx.conversation_id,
                        len(tool_calls),
                    )
                    response_text = (
                        "I noticed I was repeating the same tool call without making progress. "
                        "I've stopped to avoid getting stuck in a loop. "
                        "Please rephrase your request or be more specific about what you need."
                    )
                    break

                previous_tool_calls = tool_calls

                if not previous_response_id:
                    metrics["failures"] += 1
                    yield SSEEvent(type="error", message="LLM returned tool_calls but no response_id.")
                    yield SSEEvent(type="done", conversation_id=ctx.conversation_id)
                    return

                logging.info(
                    "FunctionCallingProcessor(streaming): tool_call iteration=%d/%d agent=%s session_id=%s tool_count=%d prev_response_id=%s",
                    iteration,
                    ctx.max_iterations,
                    ctx.agent_name,
                    ctx.conversation_id,
                    len(tool_calls),
                    previous_response_id,
                )

                # ── INJECTION A: yield tool_call events before execution ──
                for tc in tool_calls:
                    yield SSEEvent(type="tool_call", tool_name=tc.name, call_id=tc.call_id)

                # Execute tools (reuse existing logic)
                try:
                    tool_output_items, raw_results = self._execute_tool_calls(
                        tool_calls=tool_calls,
                        primary_agent=primary_agent,
                        secondary_agent=secondary_agent,
                        processor_factory=processor_factory,
                        account=account,
                        ctx=ctx,
                        metrics=metrics,
                    )
                except (ToolHandlerError, ToolResultTooLargeError) as e:
                    # ── Yield tool_result failure for each pending tool ──
                    for tc in tool_calls:
                        yield SSEEvent(type="tool_result", call_id=tc.call_id, ok=False)
                    yield SSEEvent(type="error", message=str(e))
                    yield SSEEvent(type="done", conversation_id=ctx.conversation_id)
                    return

                # ── INJECTION B: yield tool_result events after each result ──
                for (tc, raw_text), item in zip(raw_results, tool_output_items):
                    call_id = str(item.get("call_id", ""))
                    try:
                        result_json = json.loads(raw_text)
                        ok = result_json.get("ok", True) if isinstance(result_json, dict) else True
                        if isinstance(result_json, dict):
                            status = result_json.get("status")
                        else:
                            status = None
                    except (json.JSONDecodeError, TypeError):
                        ok = True
                        status = None

                    # Validate and infer status
                    if status not in ("success", "warning", "error"):
                        status = "success" if ok else "error"

                    yield SSEEvent(type="tool_result", call_id=call_id, ok=ok, status=status)

                # ── Phase 2+3: inspect raw results for action / image / svg keys ──
                for event in self._inspect_raw_results(raw_results):
                    yield event

                logging.info(
                    "FunctionCallingProcessor(streaming): sending %d function_call_output items chained to response_id=%s call_ids=%s",
                    len(tool_output_items),
                    previous_response_id,
                    [x.get("call_id") for x in tool_output_items],
                )

                next_input_items = tool_output_items

                if iteration >= ctx.max_iterations:
                    metrics["failures"] += 1
                    logging.error(
                        "FunctionCallingProcessor(streaming): exceeded max_function_call_iterations=%d for agent '%s' in conversation_id=%s",
                        ctx.max_iterations,
                        ctx.agent_name,
                        ctx.conversation_id,
                    )
                    response_text = (
                        "I ran into an internal limit while trying to call tools multiple times. "
                        "I may not have completed all requested actions. Please try rephrasing or splitting your request."
                    )
                    break

                # ── Provider throttle: pause between tool-call iterations ──
                provider_name = ProviderRegistry.resolve_name(ctx.model, ctx.provider)
                throttle_ms = self.config.get("provider_throttle_ms", {}).get(provider_name, 0)
                if throttle_ms > 0:
                    time.sleep(throttle_ms / 1000.0)

                continue

            # ── INJECTION C: final text (no tool calls) ──
            # Text already extracted above. Yield again with 'final' message_id
            # so the frontend can distinguish the final answer from intermediate
            # text that came alongside tool calls.
            yield SSEEvent(
                type="text",
                content=response_text,
                message_id=f"msg-{ctx.conversation_id}-final",
            )
            response_text = ""  # prevent post-loop duplicate yield
            break

        # Post-loop: yield text for early-exit paths (duplicate detection,
        # max iterations, empty response fallback) where text was set but
        # the normal INJECTION C path was not reached.
        if response_text:
            yield SSEEvent(
                type="text",
                content=response_text,
                message_id=f"msg-{ctx.conversation_id}-final",
            )

        # ── INJECTION D: completion ──
        yield SSEEvent(type="done", conversation_id=ctx.conversation_id)

        logging.info(
            "FunctionCallingProcessor(streaming): completed agent=%s session_id=%s iterations=%d response_preview=%r",
            ctx.agent_name,
            ctx.conversation_id,
            iteration,
            (response_text or "")[:80],
        )

    # ------------------------------------------------------------------
    # Chat2 storage helpers
    # ------------------------------------------------------------------

    def _ensure_chat2_session(self, ctx: _ProcessorContext) -> None:
        """Create a chat2 session if one doesn't exist for this conversation_id.

        Uses the existing conversation_id as the session_id so IDs stay
        consistent across storage layers.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        if self.chat2_store.session_exists(ctx.conversation_id):
            return
        try:
            self.chat2_store.create_session(
                user_id=ctx.account_id,
                account_name=ctx.account_id,
                agent_name=ctx.agent_name,
                session_id=ctx.conversation_id,
                friendly_name=ctx.context_name or None,
                context_name=ctx.context_name or None,
            )
            logging.info(
                "chat2: created session %s for account=%s agent=%s",
                ctx.conversation_id,
                ctx.account_id,
                ctx.agent_name,
            )
        except Exception:
            logging.exception(
                "chat2: failed to create session %s for account=%s",
                ctx.conversation_id,
                ctx.account_id,
            )

    def _write_chat2_events(
        self,
        ctx: _ProcessorContext,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Write user and assistant events to chat2 storage.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        try:
            self._ensure_chat2_session(ctx)
            user_event = ChatEvent(
                role="user",
                actor=ctx.account_id,
                kind="user_message",
                payload=user_message,
                metadata={"agent": ctx.agent_name},
            )
            assistant_event = ChatEvent(
                role="assistant",
                actor=ctx.agent_name,
                kind="assistant_message",
                payload=assistant_response,
                metadata={"agent": ctx.agent_name},
            )
            self.chat2_store.add_events(ctx.conversation_id, [user_event, assistant_event])
            logging.info(
                "chat2: wrote user+assistant events for session=%s",
                ctx.conversation_id,
            )
        except Exception:
            logging.exception(
                "chat2: failed to write events for session=%s",
                ctx.conversation_id,
            )

    def _write_streaming_chat2_events(
        self,
        ctx: _ProcessorContext,
        user_message: str,
        streamed_events: List[SSEEvent],
    ) -> None:
        """Write streaming events to chat2 storage, preserving image and tool cards.

        Best-effort: failures are logged but not propagated.
        """
        if self.chat2_store is None:
            return
        try:
            self._ensure_chat2_session(ctx)
            chat_events: List[ChatEvent] = []

            # 1. User message
            chat_events.append(ChatEvent(
                role="user",
                actor=ctx.account_id,
                kind="user_message",
                payload=user_message,
                metadata={"agent": ctx.agent_name},
            ))

            # 2. Tool calls and results
            for ev in streamed_events:
                if ev.type == "tool_call":
                    chat_events.append(ChatEvent(
                        role="assistant",
                        actor=ctx.agent_name,
                        kind="assistant_tool_call",
                        payload={"tool_name": ev.tool_name, "call_id": ev.call_id},
                        metadata={"agent": ctx.agent_name, "call_id": ev.call_id},
                    ))
                elif ev.type == "tool_result":
                    payload = {"call_id": ev.call_id, "ok": ev.ok}
                    # Persist status so the frontend ticker can show warnings in history
                    if ev.status:
                        payload["status"] = ev.status
                    chat_events.append(ChatEvent(
                        role="tool",
                        actor="system",
                        kind="tool_result",
                        payload=payload,
                        metadata={"call_id": ev.call_id},
                    ))

            # 3. Assistant text (find the last text event)
            assistant_texts = [ev for ev in streamed_events if ev.type == "text" and ev.content]
            if assistant_texts:
                # Use the last text event as the assistant response
                chat_events.append(ChatEvent(
                    role="assistant",
                    actor=ctx.agent_name,
                    kind="assistant_message",
                    payload=assistant_texts[-1].content or "",
                    metadata={"agent": ctx.agent_name},
                ))

            # 4. Images (PNG and SVG)
            for ev in streamed_events:
                if ev.type == "image":
                    if ev.format == "svg":
                        chat_events.append(ChatEvent(
                            role="assistant",
                            actor=ctx.agent_name,
                            kind="generated_image",
                            payload={
                                "format": "svg",
                                "svg_markup": ev.svg_markup,
                                "alt": ev.alt or "",
                                "width": ev.width,
                                "height": ev.height,
                            },
                            metadata={"agent": ctx.agent_name, "format": "svg"},
                        ))
                    else:
                        chat_events.append(ChatEvent(
                            role="assistant",
                            actor=ctx.agent_name,
                            kind="generated_image",
                            payload={"image_url": ev.image_url, "alt": ev.alt or "", "format": "png"},
                            metadata={"agent": ctx.agent_name, "format": "png"},
                        ))

            self.chat2_store.add_events(ctx.conversation_id, chat_events)
            logging.info(
                "chat2: wrote %d streaming events for session=%s (user+tool+text+image)",
                len(chat_events),
                ctx.conversation_id,
            )
        except Exception:
            logging.exception(
                "chat2: failed to write streaming events for session=%s",
                ctx.conversation_id,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_message(
        self,
        *,
        primary_agent: Agent,
        account: Dict[str, Any],
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[Agent] = None,
        processor_factory: Optional[Any] = None,
        image_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> str:
        start_ts = time.perf_counter()
        metrics: Dict[str, Any] = {
            "iterations": 0,
            "openai_calls": 0,
            "tool_calls": 0,
            "failures": 0,
        }

        logging.info("FunctionCallingProcessor inbound message: %s", message)

        if not primary_agent:
            metrics["failures"] += 1
            return "[FunctionCallingProcessor] Missing primary_agent configuration."

        ctx = self._build_context(
            primary_agent=primary_agent,
            account=account,
            conversation_id=conversation_id,
            context_name=context_name,
        )

        if not ctx.account_id:
            metrics["failures"] += 1
            return "[FunctionCallingProcessor] Missing account.accountId."

        # ── Determine if the model supports native image processing ──
        supports_images = self.llm_adapter.supports_image_processing(ctx.model, ctx.provider)

        logging.info(
            "FunctionCallingProcessor: start account=%s agent=%s session_id=%s context_type=%s max_iterations=%d supports_images=%s",
            ctx.account_id,
            ctx.agent_name,
            ctx.conversation_id,
            ctx.context_type,
            ctx.max_iterations,
            supports_images,
        )

        try:
            extra_system_messages = self._get_environment_system_messages()
            if extra_system_messages:
                logging.debug("FunctionCallingProcessor: injecting %d environment system message(s) from environment_prompt_block", len(extra_system_messages))

            # ── Provider prompt block: inject provider-specific rules ──
            provider_name = ProviderRegistry.resolve_name(ctx.model, ctx.provider)
            provider_block = self.config.get("provider_prompt_blocks", {}).get(provider_name, "")
            if provider_block:
                extra_system_messages.append(provider_block)
                logging.debug("FunctionCallingProcessor: injecting provider prompt block for provider=%s (%d chars)", provider_name, len(provider_block))

            prompt_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=ctx.conversation_id,
                agent_name=ctx.agent_name,
                account_name=ctx.account_id,
                context_type=ctx.context_type,
                max_prompt_chars=6000,
                context_name=ctx.context_name,
                extra_system_messages=extra_system_messages,
                image_ids=image_ids,
                file_ids=file_ids,
                supports_images=supports_images,
            )

            # Resolve tool definitions from the registry, filtered by the
            # agent.allowed_tools (hard ceiling), then narrowed only when the
            # active context carries an explicit non-empty allowed_tools list.
            # Missing/empty context list => no context restriction. Single
            # source of truth: resolve_tool_defs() — shared with the
            # /prompt_builder/metrics endpoint.
            context_state = load_context_state(self.prompt_builder, ctx.account_id, ctx.context_name)
            filtered_function_defs = resolve_tool_defs(self.registry, primary_agent, context_state)

            # --- Lazy tool selection: reduce the eligible set to the minimal
            # active subset the request is likely to need. Optimization only;
            # falls back to the full eligible set on any error or when not
            # worth selecting. ---
            filtered_function_defs = self._resolve_active_function_defs(
                message=message,
                filtered_function_defs=filtered_function_defs,
                ctx=ctx,
                metrics=metrics,
            )

            # --- Context mandatory tools: guarantee that tools declared via
            # context frontmatter `mandatory_tools:` are present even when
            # lazy selection dropped them or the user's request did not
            # mention them. Names are resolved to defs, deduped, and clamped
            # to agent.allowed_tools (hard ceiling). ---
            filtered_function_defs = merge_mandatory_tools(
                function_defs=filtered_function_defs,
                context_state=context_state,
                registry=self.registry,
                agent=primary_agent,
            )


            # --- Handler schema budget guardrail: trim from the tail when the
            # serialized tool schemas exceed the configured cap. Guardrail only -
            # never a selection mechanism. ---
            filtered_function_defs = apply_handler_schema_budget(
                filtered_function_defs,
                self.config,
                agent_name=ctx.agent_name,
            )

            # --- Measure handler definitions tokens and combine with prompt breakdown ---
            _log_token_breakdown(ctx, self.prompt_builder, filtered_function_defs)

            response_text = self._run_llm_loop(
                ctx=ctx,
                prompt_messages=prompt_messages,
                function_defs=filtered_function_defs,
                primary_agent=primary_agent,
                secondary_agent=secondary_agent,
                processor_factory=processor_factory,
                account=account,
                metrics=metrics,
            )

            if ctx.store_this_call and response_text:
                # Write to chat2 only (v1 removed — no backward compatibility)
                self._write_chat2_events(ctx, message, response_text)

            return response_text

        except ToolHandlerError:
            raise

        except Exception as e:
            metrics["failures"] += 1
            logging.exception(
                "FunctionCallingProcessor: unhandled error agent=%s session_id=%s",
                ctx.agent_name,
                ctx.conversation_id,
            )

            error_message = "I ran into an internal error while processing your request. The issue has been logged."

            try:
                # Write error events to chat2 only
                self._write_chat2_events(ctx, message, error_message + f" (Details: {type(e).__name__})")
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor: failed to store error conversation for session_id=%s",
                    ctx.conversation_id,
                )

            raise

        finally:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            logging.info(
                "FunctionCallingProcessor summary: agent=%s session_id=%s account=%s iterations=%d openai_calls=%d tool_calls=%d failures=%d latency_ms=%d",
                ctx.agent_name if "ctx" in locals() else "unknown",
                ctx.conversation_id if "ctx" in locals() else "unknown",
                ctx.account_id if "ctx" in locals() else "unknown",
                metrics.get("iterations", 0),
                metrics.get("openai_calls", 0),
                metrics.get("tool_calls", 0),
                metrics.get("failures", 0),
                latency_ms,
            )

    # ------------------------------------------------------------------
    # Streaming public API
    # ------------------------------------------------------------------

    def process_message_streaming(
        self,
        *,
        primary_agent: Agent,
        account: Dict[str, Any],
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[Agent] = None,
        processor_factory: Optional[Any] = None,
        image_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> Generator[str, None, None]:
        """Streaming variant of process_message.

        Same setup as process_message() but calls _run_llm_loop_streaming
        and yields SSE-formatted strings ("data: {json}\n\n").

        Collects all SSE events during streaming so they can be persisted
        to chat2 storage (including image and tool cards).
        """
        start_ts = time.perf_counter()
        metrics: Dict[str, Any] = {
            "iterations": 0,
            "openai_calls": 0,
            "tool_calls": 0,
            "failures": 0,
        }

        logging.info("FunctionCallingProcessor(streaming) inbound message: %s", message)

        if not primary_agent:
            metrics["failures"] += 1
            yield SSEEvent(type="error", message="Missing primary_agent configuration.").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

        ctx = self._build_context(
            primary_agent=primary_agent,
            account=account,
            conversation_id=conversation_id,
            context_name=context_name,
        )

        if not ctx.account_id:
            metrics["failures"] += 1
            yield SSEEvent(type="error", message="Missing account.accountId.").to_sse()
            yield SSEEvent(type="done").to_sse()
            return

        # ── Determine if the model supports native image processing ──
        supports_images = self.llm_adapter.supports_image_processing(ctx.model, ctx.provider)

        logging.info(
            "FunctionCallingProcessor(streaming): start account=%s agent=%s session_id=%s context_type=%s max_iterations=%d supports_images=%s",
            ctx.account_id,
            ctx.agent_name,
            ctx.conversation_id,
            ctx.context_type,
            ctx.max_iterations,
            supports_images,
        )

        # Collect all SSE events for chat2 persistence
        streamed_events: List[SSEEvent] = []
        events_persisted = False

        try:
            extra_system_messages = self._get_environment_system_messages()
            if extra_system_messages:
                logging.debug("FunctionCallingProcessor(streaming): injecting %d environment system message(s) from environment_prompt_block", len(extra_system_messages))

            # ── Provider prompt block: inject provider-specific rules ──
            provider_name = ProviderRegistry.resolve_name(ctx.model, ctx.provider)
            provider_block = self.config.get("provider_prompt_blocks", {}).get(provider_name, "")
            if provider_block:
                extra_system_messages.append(provider_block)
                logging.debug("FunctionCallingProcessor(streaming): injecting provider prompt block for provider=%s (%d chars)", provider_name, len(provider_block))

            prompt_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=ctx.conversation_id,
                agent_name=ctx.agent_name,
                account_name=ctx.account_id,
                context_type=ctx.context_type,
                max_prompt_chars=6000,
                context_name=ctx.context_name,
                extra_system_messages=extra_system_messages,
                image_ids=image_ids,
                file_ids=file_ids,
                supports_images=supports_images,
            )

            # Resolve tool definitions from the registry, filtered by the
            # agent.allowed_tools (hard ceiling), then narrowed only when the
            # active context carries an explicit non-empty allowed_tools list.
            # Missing/empty context list => no context restriction. Single
            # source of truth: resolve_tool_defs() — shared with the
            # /prompt_builder/metrics endpoint.
            context_state = load_context_state(self.prompt_builder, ctx.account_id, ctx.context_name)
            filtered_function_defs = resolve_tool_defs(self.registry, primary_agent, context_state)

            # --- Lazy tool selection: reduce the eligible set to the minimal
            # active subset the request is likely to need. Optimization only;
            # falls back to the full eligible set on any error or when not
            # worth selecting. ---
            filtered_function_defs = self._resolve_active_function_defs(
                message=message,
                filtered_function_defs=filtered_function_defs,
                ctx=ctx,
                metrics=metrics,
            )

            # --- Context mandatory tools: guarantee that tools declared via
            # context frontmatter `mandatory_tools:` are present even when
            # lazy selection dropped them or the user's request did not
            # mention them. Names are resolved to defs, deduped, and clamped
            # to agent.allowed_tools (hard ceiling). ---
            filtered_function_defs = merge_mandatory_tools(
                function_defs=filtered_function_defs,
                context_state=context_state,
                registry=self.registry,
                agent=primary_agent,
            )


            # --- Handler schema budget guardrail: trim from the tail when the
            # serialized tool schemas exceed the configured cap. Guardrail only -
            # never a selection mechanism. ---
            filtered_function_defs = apply_handler_schema_budget(
                filtered_function_defs,
                self.config,
                agent_name=ctx.agent_name,
            )

            # --- Measure handler definitions tokens and combine with prompt breakdown ---
            _log_token_breakdown(ctx, self.prompt_builder, filtered_function_defs)

            # Yield SSE events from the streaming loop
            for event in self._run_llm_loop_streaming(
                ctx=ctx,
                prompt_messages=prompt_messages,
                function_defs=filtered_function_defs,
                primary_agent=primary_agent,
                secondary_agent=secondary_agent,
                processor_factory=processor_factory,
                account=account,
                metrics=metrics,
            ):
                streamed_events.append(event)
                yield event.to_sse()

            # Write all collected events to chat2 storage
            if ctx.store_this_call:
                self._write_streaming_chat2_events(ctx, message, streamed_events)
                events_persisted = True

        except ToolHandlerError:
            yield SSEEvent(type="error", message="A tool execution error occurred.").to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()
            raise

        except Exception as e:
            metrics["failures"] += 1
            logging.exception(
                "FunctionCallingProcessor(streaming): unhandled error agent=%s session_id=%s",
                ctx.agent_name,
                ctx.conversation_id,
            )

            error_message = "I ran into an internal error while processing your request. The issue has been logged."

            try:
                self._write_chat2_events(ctx, message, error_message + f" (Details: {type(e).__name__})")
                events_persisted = True
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor(streaming): failed to store error conversation for session_id=%s",
                    ctx.conversation_id,
                )

            yield SSEEvent(type="error", message=error_message).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()

        finally:
            # Best-effort: if the client disconnected mid-stream (GeneratorExit),
            # persist whatever was streamed so far so history is not lost.
            if not events_persisted and ctx.store_this_call:
                self._write_streaming_chat2_events(ctx, message, streamed_events)

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            logging.info(
                "FunctionCallingProcessor(streaming) summary: agent=%s session_id=%s account=%s iterations=%d openai_calls=%d tool_calls=%d failures=%d latency_ms=%d",
                ctx.agent_name if "ctx" in locals() else "unknown",
                ctx.conversation_id if "ctx" in locals() else "unknown",
                ctx.account_id if "ctx" in locals() else "unknown",
                metrics.get("iterations", 0),
                metrics.get("openai_calls", 0),
                metrics.get("tool_calls", 0),
                metrics.get("failures", 0),
                latency_ms,
            )
