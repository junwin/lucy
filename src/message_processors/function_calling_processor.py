try:
    from injector import inject, noninjectable
except Exception:
    # Minimal shim for environments without the "injector" package (tests run in minimal environments).
    # The shim simply returns the function unchanged so the decorator has no effect.
    def inject(func):
        return func

    def noninjectable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
import contextvars
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Generator, NamedTuple
import json
import os
import time
import uuid

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.message_processors.sse_events import SSEEvent
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.handlers.handler_registry import HandlerRegistry, filter_eligible_tool_defs
from src.agent import Agent
from src.agent.agent_manager import AgentManager

from galet.adapter_interface import LLMAdapter
from galet.provider_registry import ProviderRegistry

from src.chat2.facade import Chat2Store

from src.message_processors.fcp_models import ProcessorContext, ToolHandlerError, DEFAULT_MAX_HANDLER_SCHEMA_TOKENS
from src.message_processors.fcp_chat2 import Chat2Recorder

# Import token estimator from prompt_builder
from src.prompt_builders.prompt_builder import estimate_tokens_from_text

from src.tool_selection import ToolSelectionError, ToolSelectionPipeline
from src.message_processors.fcp_tool_executor import ToolExecutor, load_context_state
from src.message_processors.fcp_loop import LLMLoopRunner
from src.message_processors.run_metrics import RunMetrics
from src.metrics import CorrelationLogHandler, RunMetricsLogger


_correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "fcp_correlation_id", default="-"
)


class _CorrelationIdFilter(logging.Filter):
    """Inject the active FCP correlation id into log records.

    Same pattern as RequestIdFilter in app.py: a filter attached to the
    correlation handler stamps a contextvar-backed id onto every record so
    the handler can attribute ERROR/WARNING counts to the active run.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id_var.get("-")
        return True


_CORRELATION_HANDLER = CorrelationLogHandler()
_CORRELATION_HANDLER.addFilter(_CorrelationIdFilter())


def _utc_now_iso() -> str:
    """Return the current UTC time as ISO-8601 with milliseconds and a Z suffix."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _resolve_metrics_logger(config: Any) -> Optional[RunMetricsLogger]:
    """Resolve the runs log logger from config, or None when unconfigured.

    Priority: explicit ``metrics_runs_log_path``, then the design default
    ``<storage_root_path>/<storage_namespace>/metrics/runs.jsonl``.
    """

    if config is None:
        return None
    path = config.get("metrics_runs_log_path")
    if not path:
        storage_root = config.get("storage_root_path")
        if storage_root:
            path = os.path.join(
                str(storage_root),
                str(config.get("storage_namespace") or ""),
                "metrics",
                "runs.jsonl",
            )
    if not path:
        return None
    return RunMetricsLogger(path)


def _compute_prompt_token_breakdown(prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Compute token counts for all prompt sections including handler definitions.

    Guarded against Mock objects in tests: if prompt_builder doesn't have a real
    breakdown dict, returns zeros across the board. Handlers use the shared
    _handler_schema_tokens() estimator so all callers agree on the same count.
    """
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

    try:
        handler_tokens = _handler_schema_tokens(filtered_function_defs)
    except Exception:
        handler_tokens = 0

    return {
        "system": system_tokens,
        "handlers": handler_tokens,
        "context": context_tokens,
        "obsidian": obsidian_tokens,
        "digest": digest_tokens,
        "history": history_tokens,
        "user": user_tokens,
        "total": total_without_handlers + handler_tokens,
    }


def _log_token_breakdown(ctx: ProcessorContext, prompt_builder: Any, filtered_function_defs: List[Dict[str, Any]]) -> Dict[str, int]:
    """Measure and log token counts for all prompt sections including handler definitions.

    Calls _compute_prompt_token_breakdown() once and returns the breakdown dict
    so callers can reuse it without recomputing.
    """
    breakdown = _compute_prompt_token_breakdown(prompt_builder, filtered_function_defs)

    logging.info(
        "Prompt.token_breakdown: agent=%s account=%s session=%s system=%d handlers=%d context=%d obsidian=%d digest=%d history=%d user=%d total=%d",
        ctx.agent_name,
        ctx.account_id,
        ctx.conversation_id,
        breakdown["system"],
        breakdown["handlers"],
        breakdown["context"],
        breakdown["obsidian"],
        breakdown["digest"],
        breakdown["history"],
        breakdown["user"],
        breakdown["total"],
    )
    return breakdown


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


class _PromptSetupResult(NamedTuple):
    prompt_messages: List[Dict[str, Any]]
    filtered_function_defs: List[Dict[str, Any]]
    supports_images: bool


class FCPResult(NamedTuple):
    text: str
    metrics: RunMetrics


def _build_run_metrics(
    metrics: Dict[str, Any],
    ctx: Optional[ProcessorContext],
    correlation_id: str,
    latency_ms: int,
    started: str = "",
    errors: int = 0,
    warnings: int = 0,
) -> RunMetrics:
    failures = metrics.get("failures", 0)
    hit_iteration_cap = metrics.get("hit_iteration_cap", False)
    return RunMetrics(
        correlation_id=correlation_id,
        iterations=metrics.get("iterations", 0),
        max_iterations=ctx.max_iterations if ctx is not None else 0,
        hit_iteration_cap=hit_iteration_cap,
        openai_calls=metrics.get("openai_calls", 0),
        tool_calls=metrics.get("tool_calls", 0),
        prompt_tokens=metrics.get("prompt_tokens", 0),
        completion_tokens=metrics.get("completion_tokens", 0),
        total_tokens=metrics.get("total_tokens", 0),
        failures=failures,
        duration_ms=latency_ms,
        agent=ctx.agent_name if ctx is not None else "",
        account=ctx.account_id if ctx is not None else "",
        session_id=ctx.conversation_id if ctx is not None else "",
        started=started,
        errors=errors,
        warnings=warnings,
        success=not (hit_iteration_cap or failures > 0),
    )


class FunctionCallingProcessor(MessageProcessorInterface):
    @inject
    @noninjectable("metrics_logger", "correlation_log_handler")
    def __init__(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: LLMAdapter,
        chat2_store: Optional[Chat2Store] = None,
        agent_manager: Optional[AgentManager] = None,
        metrics_logger: Optional[RunMetricsLogger] = None,
        correlation_log_handler: Optional[CorrelationLogHandler] = None,
    ):
        self.config = config
        self.registry = registry
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter
        self.chat2_store = chat2_store
        self.chat2 = Chat2Recorder(chat2_store)
        self.agent_manager = agent_manager
        self.tool_executor = ToolExecutor(
            registry=self.registry,
            config=self.config,
            prompt_builder=self.prompt_builder,
            llm_adapter=self.llm_adapter,
            agent_manager=self.agent_manager,
            chat2_store=self.chat2_store,
        )
        self.loop_runner = LLMLoopRunner(
            llm_adapter=self.llm_adapter,
            config=self.config,
            tool_executor=self.tool_executor,
        )
        self._metrics_logger = metrics_logger or _resolve_metrics_logger(config)
        self._correlation_handler = correlation_log_handler or _CORRELATION_HANDLER
        if not any(
            isinstance(f, _CorrelationIdFilter) for f in self._correlation_handler.filters
        ):
            self._correlation_handler.addFilter(_CorrelationIdFilter())
        root_logger = logging.getLogger()
        if self._correlation_handler not in root_logger.handlers:
            root_logger.addHandler(self._correlation_handler)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    def _resolve_tool_defs_pipeline(
        self,
        *,
        primary_agent: Agent,
        ctx: ProcessorContext,
        message: str,
    ) -> List[Dict[str, Any]]:
        """Resolve active tool defs via the tool-selection pipeline (issue #126).

        The pipeline owns tool-list resolution end to end: agent.allowed_tools
        (permission) → registry ∩ allowed (eligible) → context required tools →
        LLM prompt-based subset → schema budget. It replaces the FCP's previous
        four-step sequence (resolve_tool_defs → lazy selection →
        mandatory-tool merge → apply_handler_schema_budget).

        Unlike the old path, the pipeline raises ToolSelectionError on
        required-tool validation failures and on budget overflow (no silent
        skip / trim). Those propagate to the caller, which surfaces the
        human-readable message to the user.
        """
        pipeline = ToolSelectionPipeline(
            registry=self.registry,
            storage=getattr(self.prompt_builder, "storage", None),
            llm_adapter=self.llm_adapter,
            config=self.config,
        )
        return pipeline.get_tool_handler_defs(
            agent=primary_agent,
            account_name=ctx.account_id,
            context_name=ctx.context_name,
            prompt_text=message,
        )

    def _prepare_prompt_and_tools(
        self,
        *,
        ctx: ProcessorContext,
        primary_agent: Agent,
        message: str,
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
        supports_images: Optional[bool] = None,
        correlation_id: Optional[str] = None,
    ) -> _PromptSetupResult:
        if supports_images is None:
            supports_images = self.llm_adapter.supports_image_processing(ctx.model, ctx.provider)

        extra_system_messages = self._get_environment_system_messages()
        if extra_system_messages:
            logging.debug("FunctionCallingProcessor: injecting %d environment system message(s) from environment_prompt_block", len(extra_system_messages))

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

        filtered_function_defs = self._resolve_tool_defs_pipeline(
            primary_agent=primary_agent,
            ctx=ctx,
            message=message,
        )

        breakdown = _log_token_breakdown(ctx, self.prompt_builder, filtered_function_defs)
        if ctx.store_this_call:
            self.chat2.write_prompt_report(ctx, breakdown, correlation_id=correlation_id)

        return _PromptSetupResult(
            prompt_messages=prompt_messages,
            filtered_function_defs=filtered_function_defs,
            supports_images=supports_images,
        )


    # ------------------------------------------------------------------
    # Chat2 storage helpers
    # ------------------------------------------------------------------


    def _write_streaming_chat2_events(
        self,
        ctx: ProcessorContext,
        user_message: str,
        streamed_events: List[SSEEvent],
        correlation_id: Optional[str] = None,
    ) -> None:
        self.chat2.chat2_store = self.chat2_store
        self.chat2.write_streaming_events(
            ctx, user_message, streamed_events, correlation_id=correlation_id
        )

    def _finalize_run(
        self,
        metrics: Dict[str, Any],
        ctx: Optional[ProcessorContext],
        correlation_id: str,
        started: str,
        latency_ms: int,
        correlation_token: Optional[contextvars.Token] = None,
    ) -> RunMetrics:
        """End correlation-scoped counting and persist the run metrics record.

        Deregisters the run's ERROR/WARNING accumulator, reads the final
        counts, builds the RunMetrics record with the envelope fields, and
        appends it to the runs log when a logger is configured. Appending is
        best-effort: a log write failure never fails the request.
        """

        context = self._correlation_handler.end_run(correlation_id)
        if correlation_token is not None:
            _correlation_id_var.reset(correlation_token)
        errors = context.errors if context is not None else 0
        warnings = context.warnings if context is not None else 0
        record = _build_run_metrics(
            metrics,
            ctx,
            correlation_id,
            latency_ms,
            started=started,
            errors=errors,
            warnings=warnings,
        )
        if self._metrics_logger is not None:
            try:
                self._metrics_logger.append(record)
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor: failed to append run metrics record correlation_id=%s",
                    correlation_id,
                )
        return record

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
        correlation_id: Optional[str] = None,
    ) -> FCPResult:
        start_ts = time.perf_counter()
        metrics: Dict[str, Any] = {
            "iterations": 0,
            "openai_calls": 0,
            "tool_calls": 0,
            "failures": 0,
            "hit_iteration_cap": False,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        started = _utc_now_iso()
        self._correlation_handler.start_run(correlation_id)
        correlation_token = _correlation_id_var.set(correlation_id)

        logging.info("FunctionCallingProcessor inbound message: %s", message)

        if not primary_agent:
            metrics["failures"] += 1
            record = self._finalize_run(
                metrics, None, correlation_id, started, 0, correlation_token
            )
            return FCPResult(
                text="[FunctionCallingProcessor] Missing primary_agent configuration.",
                metrics=record,
            )

        ctx = ProcessorContext.from_agent(
            primary_agent=primary_agent,
            account=account,
            conversation_id=conversation_id,
            context_name=context_name,
        )

        if not ctx.account_id:
            metrics["failures"] += 1
            record = self._finalize_run(
                metrics, None, correlation_id, started, 0, correlation_token
            )
            return FCPResult(
                text="[FunctionCallingProcessor] Missing account.accountId.",
                metrics=record,
            )

        try:
            setup = self._prepare_prompt_and_tools(
                ctx=ctx,
                primary_agent=primary_agent,
                message=message,
                image_ids=image_ids,
                file_ids=file_ids,
                correlation_id=correlation_id,
            )

            logging.info(
                "FunctionCallingProcessor: start account=%s agent=%s session_id=%s context_type=%s max_iterations=%d supports_images=%s",
                ctx.account_id,
                ctx.agent_name,
                ctx.conversation_id,
                ctx.context_type,
                ctx.max_iterations,
                setup.supports_images,
            )

            response_text = ""
            error_message = None
            self.tool_executor.chat2_store = self.chat2_store
            for event in self.loop_runner.run(
                ctx=ctx,
                prompt_messages=setup.prompt_messages,
                function_defs=setup.filtered_function_defs,
                primary_agent=primary_agent,
                secondary_agent=secondary_agent,
                processor_factory=processor_factory,
                account=account,
                metrics=metrics,
                correlation_id=correlation_id,
            ):
                if event.type == "text" and event.content:
                    response_text = event.content
                elif event.type == "error":
                    error_message = event.message

            if error_message is not None:
                raise ToolHandlerError(error_message)

            if ctx.store_this_call and response_text:
                # Write to chat2 only (v1 removed — no backward compatibility)
                self._write_streaming_chat2_events(
                    ctx,
                    message,
                    [SSEEvent(type="text", content=response_text)],
                    correlation_id=correlation_id,
                )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            record = self._finalize_run(
                metrics, ctx, correlation_id, started, latency_ms, correlation_token
            )
            return FCPResult(
                text=response_text,
                metrics=record,
            )

        except ToolHandlerError:
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            self._finalize_run(
                metrics, ctx, correlation_id, started, latency_ms, correlation_token
            )
            raise

        except ToolSelectionError as e:
            metrics["failures"] += 1
            logging.error(
                "FunctionCallingProcessor: tool selection error agent=%s session_id=%s code=%s: %s",
                ctx.agent_name,
                ctx.conversation_id,
                e.code,
                e.message,
            )
            try:
                self._write_streaming_chat2_events(
                    ctx,
                    message,
                    [SSEEvent(type="text", content=e.message)],
                    correlation_id=correlation_id,
                )
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor: failed to store tool-selection error for session_id=%s",
                    ctx.conversation_id,
                )
            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            record = self._finalize_run(
                metrics, ctx, correlation_id, started, latency_ms, correlation_token
            )
            return FCPResult(
                text=e.message,
                metrics=record,
            )

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
                self._write_streaming_chat2_events(
                    ctx,
                    message,
                    [SSEEvent(type="text", content=error_message + f" (Details: {type(e).__name__})")],
                    correlation_id=correlation_id,
                )
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor: failed to store error conversation for session_id=%s",
                    ctx.conversation_id,
                )

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            self._finalize_run(
                metrics, ctx, correlation_id, started, latency_ms, correlation_token
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
        correlation_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Streaming variant of process_message.

        Same setup as process_message() but runs the LLMLoopRunner
        and yields SSE-formatted strings ("data: {json}\\n\\n").

        Collects all SSE events during streaming so they can be persisted
        to chat2 storage (including image and tool cards).
        """
        start_ts = time.perf_counter()
        metrics: Dict[str, Any] = {
            "iterations": 0,
            "openai_calls": 0,
            "tool_calls": 0,
            "failures": 0,
            "hit_iteration_cap": False,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        started = _utc_now_iso()
        self._correlation_handler.start_run(correlation_id)
        correlation_token = _correlation_id_var.set(correlation_id)

        logging.info(
            "FunctionCallingProcessor(streaming) inbound message: correlation_id=%s message=%s",
            correlation_id,
            message,
        )

        if not primary_agent:
            metrics["failures"] += 1
            yield SSEEvent(type="error", message="Missing primary_agent configuration.").to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done").to_sse()
            self._finalize_run(
                metrics, None, correlation_id, started, 0, correlation_token
            )
            return

        ctx = ProcessorContext.from_agent(
            primary_agent=primary_agent,
            account=account,
            conversation_id=conversation_id,
            context_name=context_name,
        )

        if not ctx.account_id:
            metrics["failures"] += 1
            yield SSEEvent(type="error", message="Missing account.accountId.").to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done").to_sse()
            self._finalize_run(
                metrics, None, correlation_id, started, 0, correlation_token
            )
            return

        # ── Determine if the model supports native image processing ──
        supports_images = self.llm_adapter.supports_image_processing(ctx.model, ctx.provider)

        logging.info(
            "FunctionCallingProcessor(streaming): start correlation_id=%s account=%s agent=%s session_id=%s context_type=%s max_iterations=%d supports_images=%s",
            correlation_id,
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
            setup = self._prepare_prompt_and_tools(
                ctx=ctx,
                primary_agent=primary_agent,
                message=message,
                image_ids=image_ids,
                file_ids=file_ids,
                correlation_id=correlation_id,
                supports_images=supports_images,
            )

            self.tool_executor.chat2_store = self.chat2_store
            for event in self.loop_runner.run(
                ctx=ctx,
                prompt_messages=setup.prompt_messages,
                function_defs=setup.filtered_function_defs,
                primary_agent=primary_agent,
                secondary_agent=secondary_agent,
                processor_factory=processor_factory,
                account=account,
                metrics=metrics,
                correlation_id=correlation_id,
            ):
                streamed_events.append(event)
                yield event.to_sse()

            # Write all collected events to chat2 storage
            if ctx.store_this_call:
                self._write_streaming_chat2_events(ctx, message, streamed_events, correlation_id=correlation_id)
                events_persisted = True

        except ToolHandlerError:
            yield SSEEvent(type="error", message="A tool execution error occurred.").to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()
            raise

        except ToolSelectionError as e:
            metrics["failures"] += 1
            logging.error(
                "FunctionCallingProcessor(streaming): tool selection error correlation_id=%s agent=%s session_id=%s code=%s: %s",
                correlation_id,
                ctx.agent_name,
                ctx.conversation_id,
                e.code,
                e.message,
            )
            try:
                self._write_streaming_chat2_events(
                    ctx,
                    message,
                    [SSEEvent(type="text", content=e.message)],
                    correlation_id=correlation_id,
                )
                events_persisted = True
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor(streaming): failed to store tool-selection error for session_id=%s",
                    ctx.conversation_id,
                )
            yield SSEEvent(type="error", message=e.message).to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()

        except Exception as e:
            metrics["failures"] += 1
            logging.exception(
                "FunctionCallingProcessor(streaming): unhandled error correlation_id=%s agent=%s session_id=%s",
                correlation_id,
                ctx.agent_name,
                ctx.conversation_id,
            )

            error_message = "I ran into an internal error while processing your request. The issue has been logged."

            try:
                self._write_streaming_chat2_events(
                    ctx,
                    message,
                    [SSEEvent(type="text", content=error_message + f" (Details: {type(e).__name__})")],
                    correlation_id=correlation_id,
                )
                events_persisted = True
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor(streaming): failed to store error conversation for session_id=%s",
                    ctx.conversation_id,
                )

            yield SSEEvent(type="error", message=error_message).to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()

        finally:
            # Best-effort: if the client disconnected mid-stream (GeneratorExit),
            # persist whatever was streamed so far so history is not lost.
            if not events_persisted and ctx.store_this_call:
                self._write_streaming_chat2_events(ctx, message, streamed_events, correlation_id=correlation_id)

            latency_ms = int((time.perf_counter() - start_ts) * 1000)
            self._finalize_run(
                metrics, ctx, correlation_id, started, latency_ms, correlation_token
            )
            logging.info(
                "FunctionCallingProcessor(streaming) summary: correlation_id=%s agent=%s session_id=%s account=%s iterations=%d openai_calls=%d tool_calls=%d failures=%d latency_ms=%d",
                correlation_id,
                ctx.agent_name if "ctx" in locals() else "unknown",
                ctx.conversation_id if "ctx" in locals() else "unknown",
                ctx.account_id if "ctx" in locals() else "unknown",
                metrics.get("iterations", 0),
                metrics.get("openai_calls", 0),
                metrics.get("tool_calls", 0),
                metrics.get("failures", 0),
                latency_ms,
            )
