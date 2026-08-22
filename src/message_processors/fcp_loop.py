import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.agent import Agent
from src.config_manager import ConfigManager
from src.llm.adapter_interface import LLMAdapter
from src.llm.provider_registry import ProviderRegistry
from src.message_processors.fcp_models import (
    ProcessorContext,
    ToolHandlerError,
    ToolResultTooLargeError,
    _ToolCall,
)
from src.message_processors.fcp_tool_executor import ToolExecutor
from src.message_processors.sse_events import SSEEvent


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

            if "action" in parsed:
                yield SSEEvent(
                    type="action",
                    action=parsed["action"],
                    action_payload=parsed.get("action_payload"),
                )

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

            if "image" in parsed and "svg" not in parsed:
                img = parsed["image"]
                if isinstance(img, dict):
                    yield SSEEvent(
                        type="image",
                        format="png",
                        image_url=img.get("url"),
                        alt=img.get("alt"),
                    )

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
    ) -> Generator[SSEEvent, None, None]:
        """Single streaming-native agentic loop yielding SSEEvent objects.

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
                tool_calls = self.tool_executor.wrap_tool_calls(tool_calls_raw)

                logging.info(
                    "FunctionCallingProcessor(streaming): raw tool calls agent=%s session_id=%s iteration=%d raw=%r wrapped=%r",
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

            response_text = self.llm_adapter.get_text(llm_response)
            if response_text:
                yield SSEEvent(
                    type="text",
                    content=response_text,
                    message_id=f"msg-{ctx.conversation_id}-iter-{iteration}",
                )

            if tool_calls:
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
                    )
                except (ToolHandlerError, ToolResultTooLargeError) as e:
                    for tc in tool_calls:
                        yield SSEEvent(type="tool_result", call_id=tc.call_id, ok=False)
                    yield SSEEvent(type="error", message=str(e))
                    yield SSEEvent(type="done", conversation_id=ctx.conversation_id)
                    return

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

                    if status not in ("success", "warning", "error"):
                        status = "success" if ok else "error"

                    yield SSEEvent(type="tool_result", call_id=call_id, ok=ok, status=status)

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

        yield SSEEvent(type="done", conversation_id=ctx.conversation_id)

        logging.info(
            "FunctionCallingProcessor(streaming): completed agent=%s session_id=%s iterations=%d response_preview=%r",
            ctx.agent_name,
            ctx.conversation_id,
            iteration,
            (response_text or "")[:80],
        )
