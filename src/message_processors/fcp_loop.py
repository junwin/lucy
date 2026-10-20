import logging
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.agent import Agent
from src.config_manager import ConfigManager
from galet.adapter_interface import LLMAdapter
from galet.dto import LLMUsage
from galet.provider_registry import ProviderRegistry
from src.message_processors.fcp_models import (
    ProcessorContext,
    ToolHandlerError,
    ToolResultTooLargeError,
    _ToolCall,
)
from src.message_processors.fcp_tool_executor import ToolExecutor
from src.message_processors.sse_events import SSEEvent
from src.message_processors.fcp_result_events import inspect_raw_results, tool_result_events
from src.message_processors.run_metrics import record_processor_failure


class LLMLoopRunner:
    def __init__(
        self,
        *,
        llm_adapter: LLMAdapter,
        config: ConfigManager,
        tool_executor: ToolExecutor,
    ) -> None:
        self.llm_adapter = llm_adapter
        self.config = config
        self.tool_executor = tool_executor

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

    @staticmethod
    def _inspect_raw_results(
        raw_results: List[Tuple[_ToolCall, str]],
    ) -> Generator[SSEEvent, None, None]:
        """Compatibility hook for tool payload deliverables."""
        yield from inspect_raw_results(raw_results)

    def run(
        self,
        *,
        ctx: ProcessorContext,
        prompt_messages: List[Dict[str, Any]],
        function_defs: List[Dict[str, Any]],
        primary_agent: Agent,
        secondary_agent: Optional[Agent],
        processor_factory: Optional[Any],
        account: Dict[str, Any],
        metrics: Dict[str, Any],
        correlation_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Generator[SSEEvent, None, None]:
        """Single streaming-native agentic loop yielding SSEEvent objects.

        Injection points:
          A - tool_call  (before each tool executes)
          B - tool_result (after each tool completes)
          C - text        (final assistant text)
          D - done        (stream complete)
        """
        correlation_id = correlation_id or "-"
        response_text = ""
        previous_response_id: Optional[str] = None
        previous_tool_calls: Optional[List[_ToolCall]] = None
        next_input_items: List[Dict[str, Any]] = prompt_messages

        for iteration in range(1, ctx.max_iterations + 1):
            metrics["iterations"] = iteration
            metrics["openai_calls"] += 1

            MAX_EMPTY_RETRIES = 2
            llm_response = None
            tool_calls: List[_ToolCall] = []

            for retry_attempt in range(MAX_EMPTY_RETRIES + 1):
                if retry_attempt > 0:
                    metrics["openai_calls"] += 1
                    logging.warning(
                        "FCP: empty LLM response correlation_id=%s at iteration=%d, retry %d/%d agent=%s session_id=%s",
                        correlation_id, iteration, retry_attempt, MAX_EMPTY_RETRIES, ctx.agent_name, ctx.conversation_id,
                    )

                model_started = time.perf_counter()
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

                model_elapsed_ms = round((time.perf_counter() - model_started) * 1000)
                usage_getter = getattr(self.llm_adapter, "get_usage", None)
                call_usage = usage_getter(llm_response) if callable(usage_getter) else None
                input_tokens = call_usage.input_tokens if isinstance(call_usage, LLMUsage) else None
                output_tokens = call_usage.output_tokens if isinstance(call_usage, LLMUsage) else None
                total_tokens = call_usage.total_tokens if isinstance(call_usage, LLMUsage) else None
                logging.info(
                    "model_call_done correlation_id=%s agent=%s session_id=%s iteration=%d attempt=%d duration_ms=%d input_tokens=%s output_tokens=%s total_tokens=%s",
                    correlation_id, ctx.agent_name, ctx.conversation_id, iteration,
                    retry_attempt + 1, model_elapsed_ms,
                    input_tokens if input_tokens is not None else "-",
                    output_tokens if output_tokens is not None else "-",
                    total_tokens if total_tokens is not None else "-",
                )

                logging.debug(
                    "FunctionCallingProcessor(streaming): raw LLM response correlation_id=%s agent=%s session_id=%s iteration=%d type=%s llm_response=%r",
                    correlation_id,
                    ctx.agent_name,
                    ctx.conversation_id,
                    iteration,
                    type(llm_response).__name__,
                    llm_response,
                )

                if isinstance(call_usage, LLMUsage):
                    metrics["prompt_tokens"] += call_usage.input_tokens or 0
                    metrics["completion_tokens"] += call_usage.output_tokens or 0
                    metrics["total_tokens"] += call_usage.total_tokens or 0

                result_response_id = self.llm_adapter.get_response_id(llm_response)
                if result_response_id:
                    previous_response_id = result_response_id

                tool_calls_raw = self.llm_adapter.extract_tool_calls(llm_response)
                tool_calls = self.tool_executor.wrap_tool_calls(tool_calls_raw)

                logging.info(
                    "FunctionCallingProcessor(streaming): raw tool calls correlation_id=%s agent=%s session_id=%s iteration=%d raw=%r wrapped=%r",
                    correlation_id,
                    ctx.agent_name,
                    ctx.conversation_id,
                    iteration,
                    tool_calls_raw,
                    [(t.name, t.call_id, t.arguments_raw) for t in tool_calls],
                )

                if tool_calls or self.llm_adapter.get_text(llm_response):
                    break
            else:
                response_text = "I received an empty response from the model — please try again."
                logging.error(
                    "FCP: empty LLM response correlation_id=%s after %d retries at iteration=%d agent=%s session_id=%s — using fallback",
                    correlation_id, MAX_EMPTY_RETRIES, iteration, ctx.agent_name, ctx.conversation_id,
                )
                break

            logging.info(
                "FunctionCallingProcessor(streaming): iteration=%d/%d correlation_id=%s agent=%s session_id=%s response_id=%s",
                iteration,
                ctx.max_iterations,
                correlation_id,
                ctx.agent_name,
                ctx.conversation_id,
                previous_response_id,
            )

            response_text = self.llm_adapter.get_text(llm_response)
            if response_text and tool_calls:
                yield SSEEvent(
                    type="text",
                    content=response_text,
                    message_id=f"msg-{ctx.conversation_id}-iter-{iteration}",
                )

            if tool_calls:
                if self._tool_calls_are_duplicate(tool_calls, previous_tool_calls):
                    logging.warning(
                        "FunctionCallingProcessor(streaming): duplicate tool calls detected correlation_id=%s at iteration=%d/%d "
                        "agent=%s session_id=%s tool_count=%d. Breaking loop.",
                        correlation_id,
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
                    record_processor_failure(metrics)
                    yield SSEEvent(type="error", message="LLM returned tool_calls but no response_id.")
                    yield SSEEvent(type="metrics", metrics=dict(metrics))
                    yield SSEEvent(type="done", conversation_id=ctx.conversation_id)
                    return

                logging.info(
                    "FunctionCallingProcessor(streaming): tool_call iteration=%d/%d correlation_id=%s agent=%s session_id=%s tool_count=%d prev_response_id=%s",
                    iteration,
                    ctx.max_iterations,
                    correlation_id,
                    ctx.agent_name,
                    ctx.conversation_id,
                    len(tool_calls),
                    previous_response_id,
                )

                for tc in tool_calls:
                    yield SSEEvent(type="tool_call", tool_name=tc.name, call_id=tc.call_id)

                try:
                    tool_output_items, raw_results = self.tool_executor.execute_tool_calls(
                        tool_calls=tool_calls,
                        primary_agent=primary_agent,
                        secondary_agent=secondary_agent,
                        processor_factory=processor_factory,
                        account=account,
                        ctx=ctx,
                        metrics=metrics,
                        correlation_id=correlation_id,
                        trace_id=trace_id or correlation_id,
                    )
                except (ToolHandlerError, ToolResultTooLargeError) as e:
                    for tc in tool_calls:
                        yield SSEEvent(type="tool_result", call_id=tc.call_id, ok=False)
                    yield SSEEvent(type="error", message=str(e))
                    yield SSEEvent(type="metrics", metrics=dict(metrics))
                    yield SSEEvent(type="done", conversation_id=ctx.conversation_id)
                    return

                for event in tool_result_events(raw_results, tool_output_items):
                    yield event

                for event in self._inspect_raw_results(raw_results):
                    yield event

                logging.info(
                    "FunctionCallingProcessor(streaming): sending %d function_call_output items correlation_id=%s chained to response_id=%s call_ids=%s",
                    len(tool_output_items),
                    correlation_id,
                    previous_response_id,
                    [x.get("call_id") for x in tool_output_items],
                )

                activated_tools = self.tool_executor.apply_tool_activations(
                    raw_results=raw_results,
                    function_defs=function_defs,
                    primary_agent=primary_agent,
                    ctx=ctx,
                )
                if activated_tools:
                    logging.info(
                        "FunctionCallingProcessor(streaming): activated run-scoped tools "
                        "correlation_id=%s iteration=%d agent=%s session_id=%s tools=%s",
                        correlation_id,
                        iteration,
                        ctx.agent_name,
                        ctx.conversation_id,
                        activated_tools,
                    )

                next_input_items = tool_output_items

                if iteration >= ctx.max_iterations:
                    record_processor_failure(metrics)
                    logging.error(
                        "FunctionCallingProcessor(streaming): exceeded max_function_call_iterations=%d correlation_id=%s for agent '%s' in conversation_id=%s",
                        ctx.max_iterations,
                        correlation_id,
                        ctx.agent_name,
                        ctx.conversation_id,
                    )
                    response_text = (
                        "I ran into an internal limit while trying to call tools multiple times. "
                        "I may not have completed all requested actions. Please try rephrasing or splitting your request."
                    )
                    metrics["hit_iteration_cap"] = True
                    break

                provider_name = ProviderRegistry.resolve_name(ctx.model, ctx.provider)
                throttle_ms = self.config.get("provider_throttle_ms", {}).get(provider_name, 0)
                if throttle_ms > 0:
                    time.sleep(throttle_ms / 1000.0)

                continue

            yield SSEEvent(
                type="text",
                content=response_text,
                message_id=f"msg-{ctx.conversation_id}-final",
            )
            response_text = ""
            break

        if response_text:
            yield SSEEvent(
                type="text",
                content=response_text,
                message_id=f"msg-{ctx.conversation_id}-final",
            )

        yield SSEEvent(type="metrics", metrics=dict(metrics))
        yield SSEEvent(type="done", conversation_id=ctx.conversation_id)

        logging.info(
            "FunctionCallingProcessor(streaming): completed correlation_id=%s agent=%s session_id=%s iterations=%d response_preview=%r",
            correlation_id,
            ctx.agent_name,
            ctx.conversation_id,
            iteration,
            (response_text or "")[:80],
        )
