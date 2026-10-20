from src.episodic import LucyEpisodicStore
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
from typing import Optional, Dict, Any, List, Generator, NamedTuple
import time

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.message_processors.sse_events import SSEEvent
from src.message_processors.image_delivery import image_event_for_browser, image_event_for_history
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.handlers.handler_registry import HandlerRegistry
from src.agent import Agent
from src.agent.agent_manager import AgentManager

from galet.adapter_interface import LLMAdapter


from src.message_processors.fcp_models import ProcessorContext, ToolHandlerError, DEFAULT_MAX_HANDLER_SCHEMA_TOKENS
from src.message_processors.episodic_recorder import EpisodicRecorder

from src.tool_selection import ToolSelectionError, ToolSelectionPipeline
from src.message_processors.fcp_tool_executor import ToolExecutor, load_context_state
from src.message_processors.fcp_loop import LLMLoopRunner
from src.message_processors.run_metrics import RunMetrics, record_processor_failure
from src.metrics import CorrelationLogHandler, RunMetricsLogger


from src.message_processors.fcp_prompt_metrics import (
    _TOKEN_COUNTER,
    _compute_prompt_token_breakdown,
    _handler_schema_tokens,
    _log_token_breakdown,
    apply_handler_schema_budget,
    resolve_tool_defs,
)
from src.message_processors.fcp_prompt_preparation import (
    _PromptSetupResult,
    _TOOL_DISCOVERY_SYSTEM_MESSAGE,
    get_environment_system_messages,
    prepare_prompt_and_tools,
    resolve_tool_defs_pipeline,
)
from src.message_processors.fcp_run_lifecycle import (
    _CORRELATION_HANDLER,
    _CorrelationIdFilter,
    _correlation_id_var,
    _utc_now_iso,
    _resolve_metrics_logger,
    _build_run_metrics,
    begin_run,
    finalize_run,
)

class FCPResult(NamedTuple):
    text: str
    metrics: RunMetrics



class FunctionCallingProcessor(MessageProcessorInterface):
    @inject
    @noninjectable("metrics_logger", "correlation_log_handler")
    def __init__(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: LLMAdapter,
        episodic_store: Optional[LucyEpisodicStore] = None,
        agent_manager: Optional[AgentManager] = None,
        metrics_logger: Optional[RunMetricsLogger] = None,
        correlation_log_handler: Optional[CorrelationLogHandler] = None,
    ):
        self.config = config
        self.registry = registry
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter
        self.episodic_store = episodic_store
        self.episodic_recorder = EpisodicRecorder(episodic_store)
        self.agent_manager = agent_manager
        self.tool_executor = ToolExecutor(
            registry=self.registry,
            config=self.config,
            prompt_builder=self.prompt_builder,
            llm_adapter=self.llm_adapter,
            agent_manager=self.agent_manager,
            episodic_store=self.episodic_store,
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
        """Compatibility hook for server-wide environment prompt injection."""
        return get_environment_system_messages(self.config)

    def _resolve_tool_defs_pipeline(
        self,
        *,
        primary_agent: Agent,
        ctx: ProcessorContext,
        message: str,
    ) -> List[Dict[str, Any]]:
        """Compatibility hook using the existing tool-selection pipeline."""
        return resolve_tool_defs_pipeline(
            registry=self.registry,
            prompt_builder=self.prompt_builder,
            llm_adapter=self.llm_adapter,
            config=self.config,
            pipeline_factory=ToolSelectionPipeline,
            primary_agent=primary_agent,
            ctx=ctx,
            message=message,
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
        return prepare_prompt_and_tools(
            config=self.config,
            registry=self.registry,
            prompt_builder=self.prompt_builder,
            llm_adapter=self.llm_adapter,
            environment_messages=self._get_environment_system_messages,
            resolve_tools=self._resolve_tool_defs_pipeline,
            measure_tokens=_log_token_breakdown,
            ctx=ctx,
            primary_agent=primary_agent,
            message=message,
            image_ids=image_ids,
            file_ids=file_ids,
            supports_images=supports_images,
            correlation_id=correlation_id,
        )

    # ------------------------------------------------------------------
    # Episodic memory helpers
    # ------------------------------------------------------------------


    def _write_streaming_episodic_events(
        self,
        ctx: ProcessorContext,
        user_message: str,
        streamed_events: List[SSEEvent],
        correlation_id: Optional[str] = None,
        image_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> None:
        self.episodic_recorder.episodic_store = self.episodic_store
        self.episodic_recorder.write_streaming_events(
            ctx, user_message, streamed_events, correlation_id=correlation_id,
            image_ids=image_ids, file_ids=file_ids,
        )

    def _write_streaming_episodic_user_message(
        self,
        ctx: ProcessorContext,
        user_message: str,
        correlation_id: Optional[str] = None,
        image_ids: Optional[List[str]] = None,
        file_ids: Optional[List[str]] = None,
    ) -> None:
        self.episodic_recorder.episodic_store = self.episodic_store
        self.episodic_recorder.write_user_message(
            ctx, user_message, correlation_id=correlation_id,
            image_ids=image_ids, file_ids=file_ids,
        )

    def _write_streaming_episodic_event(
        self,
        ctx: ProcessorContext,
        event: SSEEvent,
        correlation_id: Optional[str] = None,
    ) -> None:
        self.episodic_recorder.episodic_store = self.episodic_store
        self.episodic_recorder.write_streaming_event(
            ctx, event, correlation_id=correlation_id
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
        return finalize_run(
            metrics, ctx, correlation_id, started, latency_ms, correlation_token,
            correlation_handler=self._correlation_handler,
            metrics_logger=self._metrics_logger,
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
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> FCPResult:
        start_ts, metrics, correlation_id, started, correlation_token = begin_run(
            self._correlation_handler, correlation_id, now=_utc_now_iso
        )

        logging.info("FunctionCallingProcessor inbound message: %s", message)

        if not primary_agent:
            record_processor_failure(metrics)
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
            record_processor_failure(metrics)
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
            if ctx.store_this_call:
                self.episodic_recorder.write_prompt_report(
                    ctx,
                    setup.prompt_breakdown,
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
            delivered_events = []
            self.tool_executor.episodic_store = self.episodic_store
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
                trace_id=trace_id or correlation_id,
            ):
                delivered_events.append(event)
                if event.type == "text" and event.content:
                    response_text = event.content
                elif event.type == "error":
                    error_message = event.message

            if error_message is not None:
                raise ToolHandlerError(error_message)

            if ctx.store_this_call and (response_text or image_ids or file_ids or delivered_events):
                self._write_streaming_episodic_events(
                    ctx,
                    message,
                    delivered_events,
                    correlation_id=correlation_id,
                    image_ids=image_ids,
                    file_ids=file_ids,
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
            record_processor_failure(metrics)
            logging.error(
                "FunctionCallingProcessor: tool selection error agent=%s session_id=%s code=%s: %s",
                ctx.agent_name,
                ctx.conversation_id,
                e.code,
                e.message,
            )
            try:
                self._write_streaming_episodic_events(
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
            record_processor_failure(metrics)
            logging.exception(
                "FunctionCallingProcessor: unhandled error agent=%s session_id=%s",
                ctx.agent_name,
                ctx.conversation_id,
            )

            error_message = "I ran into an internal error while processing your request. The issue has been logged."

            try:
                self._write_streaming_episodic_events(
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
        trace_id: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Streaming variant of process_message.

        Same setup as process_message() but runs the LLMLoopRunner
        and yields SSE-formatted strings ("data: {json}\\n\\n").

        Builds the prompt before persisting the current user message, so the
        message cannot be recalled as both history and current input. It then
        persists the user message before model work and each deliverable event
        before yielding it to the client. This keeps history recoverable when
        SSE delivery stalls or the client disconnects.
        """
        start_ts, metrics, correlation_id, started, correlation_token = begin_run(
            self._correlation_handler, correlation_id, now=_utc_now_iso
        )

        logging.info(
            "FunctionCallingProcessor(streaming) inbound message: correlation_id=%s message=%s",
            correlation_id,
            message,
        )

        if not primary_agent:
            record_processor_failure(metrics)
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
            record_processor_failure(metrics)
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

        last_persisted_text: Optional[str] = None
        delivered_images = set()

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

            if ctx.store_this_call:
                self._write_streaming_episodic_user_message(
                    ctx, message, correlation_id=correlation_id,
                    image_ids=image_ids, file_ids=file_ids,
                )
                self.episodic_recorder.write_prompt_report(
                    ctx,
                    setup.prompt_breakdown,
                    correlation_id=correlation_id,
                )

            self.tool_executor.episodic_store = self.episodic_store
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
                trace_id=trace_id or correlation_id,
            ):
                if event.type == "image":
                    image_key = event.image_id or event.message_id
                    if image_key and image_key in delivered_images:
                        continue
                    if image_key:
                        delivered_images.add(image_key)
                    event = image_event_for_history(event, ctx.account_id)
                should_persist = True
                if event.type == "text" and event.content:
                    # Preserve distinct iteration text while avoiding
                    # duplicate history messages on replay.
                    should_persist = event.content != last_persisted_text
                    if should_persist:
                        last_persisted_text = event.content
                if ctx.store_this_call and should_persist:
                    self._write_streaming_episodic_event(
                        ctx, event, correlation_id=correlation_id
                    )
                # Persist the small reference above; expand bytes only for transport.
                yield image_event_for_browser(event, self.config, ctx.account_id).to_sse()

        except ToolHandlerError:
            yield SSEEvent(type="error", message="A tool execution error occurred.").to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()
            raise

        except ToolSelectionError as e:
            record_processor_failure(metrics)
            logging.error(
                "FunctionCallingProcessor(streaming): tool selection error correlation_id=%s agent=%s session_id=%s code=%s: %s",
                correlation_id,
                ctx.agent_name,
                ctx.conversation_id,
                e.code,
                e.message,
            )
            try:
                self._write_streaming_episodic_event(
                    ctx,
                    SSEEvent(type="text", content=e.message),
                    correlation_id=correlation_id,
                )
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor(streaming): failed to store tool-selection error for session_id=%s",
                    ctx.conversation_id,
                )
            yield SSEEvent(type="error", message=e.message).to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()

        except Exception as e:
            record_processor_failure(metrics)
            logging.exception(
                "FunctionCallingProcessor(streaming): unhandled error correlation_id=%s agent=%s session_id=%s",
                correlation_id,
                ctx.agent_name,
                ctx.conversation_id,
            )

            error_message = "I ran into an internal error while processing your request. The issue has been logged."

            try:
                self._write_streaming_episodic_event(
                    ctx,
                    SSEEvent(
                        type="text",
                        content=error_message + f" (Details: {type(e).__name__})",
                    ),
                    correlation_id=correlation_id,
                )
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor(streaming): failed to store error conversation for session_id=%s",
                    ctx.conversation_id,
                )

            yield SSEEvent(type="error", message=error_message).to_sse()
            yield SSEEvent(type="metrics", metrics=dict(metrics)).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()

        finally:
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
