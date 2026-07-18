from __future__ import annotations
from dataclasses import dataclass
try:
    from injector import inject
except Exception:
    # Minimal shim for environments without the "injector" package (tests run in minimal environments).
    # The shim simply returns the function unchanged so the decorator has no effect.
    def inject(func):
        return func
import logging
from typing import Optional, Dict, Any, List, Iterable, Generator
import json
import time

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.message_processors.sse_events import SSEEvent
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.handlers.handler_registry import HandlerRegistry
from src.agent import Agent

from src.llm.adapter_interface import LLMAdapter

from src.chat2.facade import Chat2Store
from src.chat2.models import ChatEvent


class ToolResultTooLargeError(Exception):
    """Raised when a tool result exceeds the configured max_tool_result_chars."""


class ToolHandlerError(Exception):
    """Raised when a tool handler fails during execution."""


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


@dataclass(frozen=True)
class _ToolCall:
    name: str
    call_id: str
    arguments_raw: str


class FunctionCallingProcessor(MessageProcessorInterface):
    @inject
    def __init__(
        self,
        config: ConfigManager,
        registry: HandlerRegistry,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: LLMAdapter,
        chat2_store: Optional[Chat2Store] = None,
    ):
        self.config = config
        self.registry = registry
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter
        self.chat2_store = chat2_store

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


    def _execute_simple_tasklist(
        self,
        tasklist: Dict[str, Any],
        *,
        supervisor_agent: Agent,
        worker_agent: Optional[Agent],
        account: Dict[str, Any],
        conversation_id: str,
        context_name: str,
        processor_factory: Any,
        delegation_depth: int,
    ) -> Dict[str, Any]:
        max_depth = int(getattr(supervisor_agent, "max_delegation_depth", 1))
        if delegation_depth >= max_depth:
            logging.warning(
                "_execute_simple_tasklist: delegation depth %d >= max %d for agent=%s session_id=%s; refusing.",
                delegation_depth,
                max_depth,
                supervisor_agent.name,
                conversation_id,
            )
            return {"ok": False, "error": "Max delegation depth exceeded while executing the tasklist."}

        tasks = tasklist.get("tasks") or []
        if not isinstance(tasks, list):
            return {"ok": False, "error": "tasklist.tasks must be a list."}

        results: List[Dict[str, Any]] = []
        tasklist_description = tasklist.get("description") or ""

        logging.info(
            "_execute_simple_tasklist: start supervisor=%s worker=%s session_id=%s tasks=%d depth=%d/%d desc=%r",
            supervisor_agent.name,
            worker_agent.name if worker_agent else None,
            conversation_id,
            len(tasks),
            delegation_depth,
            max_depth,
            tasklist_description[:120],
        )

        for idx, task in enumerate(tasks, start=1):
            task_id = task.get("id") or f"task-{idx}"
            task_type = task.get("type", "task")
            task_agent_name = task.get("agent") or (worker_agent.name if worker_agent else "")
            task_title = task.get("title") or ""
            instruction = task.get("instruction") or ""
            file_path = task.get("file") or ""

            logging.info(
                "_execute_simple_tasklist: task %d/%d id=%s type=%s agent=%s title=%r",
                idx,
                len(tasks),
                task_id,
                task_type,
                task_agent_name,
                task_title[:80],
            )

            if task_type != "task":
                results.append({"id": task_id, "ok": False, "error": f"Unsupported task type: {task_type}"})
                continue

            if not instruction:
                results.append({"id": task_id, "ok": False, "error": "Task has no instruction to execute."})
                continue

            msg_parts = [instruction]
            if file_path:
                msg_parts.append(f"\n\nFocus file: {file_path}")
            task_message = "".join(msg_parts)

            if worker_agent and task_agent_name == worker_agent.name:
                try:
                    task_response = self.process_message(
                        primary_agent=worker_agent,
                        account=account,
                        message=task_message,
                        conversation_id=conversation_id,
                        context_name=context_name,
                        secondary_agent=None,
                        processor_factory=processor_factory,
                    )
                    results.append({"id": task_id, "ok": True, "agent": task_agent_name, "response": task_response})
                except ToolHandlerError as e:
                    logging.exception("_execute_simple_tasklist: error executing worker task id=%s", task_id)
                    results.append({"id": task_id, "ok": False, "agent": task_agent_name, "error": f"{type(e).__name__}: {e}"})
                    break
            else:
                results.append({"id": task_id, "ok": False, "agent": task_agent_name, "error": f"Unknown agent: {task_agent_name}"})

        summary = {
            "ok": all(r.get("ok") for r in results) if results else False,
            "description": tasklist_description,
            "tasks": results,
        }

        logging.info(
            "_execute_simple_tasklist: completed supervisor=%s worker=%s session_id=%s tasks=%d ok=%s",
            supervisor_agent.name,
            worker_agent.name if worker_agent else None,
            conversation_id,
            len(results),
            summary["ok"],
        )
        return summary




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
    ) -> List[Dict[str, Any]]:
        tool_output_items: List[Dict[str, Any]] = []

        # Build the shared execution context for handlers that need it
        # (e.g. TasklistsRunHandler needs primary_agent, account, conversation_id, etc.)
        # NOTE: account_name is NOT included here — it's passed explicitly to execute().
        handler_context: Dict[str, Any] = {
            "primary_agent": primary_agent,
            "secondary_agent": secondary_agent,
            "processor_factory": processor_factory,
            "account": account,
            "conversation_id": ctx.conversation_id,
            "context_name": ctx.context_name,
            "agent_name": ctx.agent_name,
            "storage": getattr(self, "_storage", None),
            "registry": self.registry,
            "prompt_builder": self.prompt_builder,
            "config": self.config,
            "chat2_store": self.chat2_store,
            "llm_adapter": self.llm_adapter,
        }

        for tc in tool_calls:
            metrics["tool_calls"] += 1

            if not tc.call_id:
                metrics["failures"] += 1
                raise ToolHandlerError(
                    f"Tool call missing id/call_id for tool '{tc.name}'. Cannot send function_call_output."
                )

            try:
                handler = self.registry.create(tc.name, config=self.config)

                logging.info(
                    "tool_execute_start tool=%s call_id=%s account=%s",
                    tc.name,
                    tc.call_id,
                    ctx.account_id,
                )

                if hasattr(handler, "execute_raw"):
                    tool_result_text = handler.execute_raw(tc.arguments_raw, account_name=ctx.account_id, call_id=tc.call_id)  # type: ignore[attr-defined]
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

                if tc.name == "delegate_tasks" and secondary_agent is not None and processor_factory is not None:
                    try:
                        maybe = json.loads(tool_result_text or "{}")
                    except Exception:
                        maybe = {}

                    if isinstance(maybe, dict) and maybe.get("ok") and maybe.get("kind") == "tasklist":
                        logging.info(
                            "FunctionCallingProcessor: executing tasklist from delegate_tasks using supervisor=%s worker=%s session_id=%s call_id=%s",
                            ctx.agent_name,
                            secondary_agent.name,
                            ctx.conversation_id,
                            tc.call_id,
                        )
                        tasklist_result = self._execute_simple_tasklist(
                            tasklist=maybe,
                            supervisor_agent=primary_agent,
                            worker_agent=secondary_agent,
                            account=account,
                            conversation_id=ctx.conversation_id,
                            context_name=ctx.context_name,
                            processor_factory=processor_factory,
                            delegation_depth=ctx.delegation_depth,
                        )
                        tool_result_text = json.dumps(tasklist_result, ensure_ascii=False)

                tool_result_text = self._tool_result_to_text(tool_result_text)

            except ToolResultTooLargeError as e:
                metrics["failures"] += 1
                tool_result_text = self._tool_result_to_text({"ok": False, "tool": tc.name, "error": str(e)})
                raise ToolResultTooLargeError(str(e)) from e   
            except Exception as e:
                metrics["failures"] += 1
                logging.exception("Tool execution failed: %s call_id=%s", tc.name, tc.call_id)
                raise ToolHandlerError(f"{type(e).__name__}: {e}")

            tool_output_items.append(self.llm_adapter.format_tool_output(call_id=str(tc.call_id), output=tool_result_text))

        return tool_output_items



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

            llm_response = self.llm_adapter.call_model(
                model=ctx.model,
                input=next_input_items,
                temperature=ctx.temperature,
                tools=function_defs,
                tool_choice="auto" if function_defs else None,
                store=ctx.store_this_call,
                metadata={"conversation_id": ctx.conversation_id, "session_id": ctx.context_name or None},
                previous_response_id=previous_response_id,
            )

            result_response_id = self.llm_adapter.get_response_id(llm_response)
            if result_response_id:
                previous_response_id = result_response_id

            logging.info(
                "FunctionCallingProcessor: iteration=%d/%d agent=%s session_id=%s response_id=%s",
                iteration,
                ctx.max_iterations,
                ctx.agent_name,
                ctx.conversation_id,
                previous_response_id,
            )

            tool_calls_raw = self.llm_adapter.extract_tool_calls(llm_response)
            tool_calls = self._wrap_tool_calls(tool_calls_raw)

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

                tool_output_items = self._execute_tool_calls(
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

            llm_response = self.llm_adapter.call_model(
                model=ctx.model,
                input=next_input_items,
                temperature=ctx.temperature,
                tools=function_defs,
                tool_choice="auto" if function_defs else None,
                store=ctx.store_this_call,
                metadata={"conversation_id": ctx.conversation_id, "session_id": ctx.context_name or None},
                previous_response_id=previous_response_id,
            )

            result_response_id = self.llm_adapter.get_response_id(llm_response)
            if result_response_id:
                previous_response_id = result_response_id

            logging.info(
                "FunctionCallingProcessor(streaming): iteration=%d/%d agent=%s session_id=%s response_id=%s",
                iteration,
                ctx.max_iterations,
                ctx.agent_name,
                ctx.conversation_id,
                previous_response_id,
            )

            tool_calls_raw = self.llm_adapter.extract_tool_calls(llm_response)
            tool_calls = self._wrap_tool_calls(tool_calls_raw)

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
                    tool_output_items = self._execute_tool_calls(
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
                for item in tool_output_items:
                    call_id = str(item.get("call_id", ""))
                    yield SSEEvent(type="tool_result", call_id=call_id, ok=True)

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

                continue

            # ── INJECTION C: final text ──
            response_text = self.llm_adapter.get_text(llm_response)
            yield SSEEvent(
                type="text",
                content=response_text,
                message_id=f"msg-{ctx.conversation_id}-final",
            )
            break

        # If no text was yielded (e.g., loop break on duplicate detection / max iterations),
        # still yield the text if we have it.
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
    # Chat2 storage helpers (v1 removed — no backward compatibility)
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

        logging.info(
            "FunctionCallingProcessor: start account=%s agent=%s session_id=%s context_type=%s max_iterations=%d",
            ctx.account_id,
            ctx.agent_name,
            ctx.conversation_id,
            ctx.context_type,
            ctx.max_iterations,
        )

        try:
            extra_system_messages = self._get_environment_system_messages()
            if extra_system_messages:
                logging.debug("FunctionCallingProcessor: injecting %d environment system message(s) from environment_prompt_block", len(extra_system_messages))

            prompt_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=ctx.conversation_id,
                agent_name=ctx.agent_name,
                account_name=ctx.account_id,
                context_type=ctx.context_type,
                max_prompt_chars=6000,
                context_name=ctx.context_name,
                extra_system_messages=extra_system_messages,
            )

            # Get the global tool definitions from the registry. We'll filter this
            # list according to the agent.allowed_tools.
            function_defs = self.registry.tools()

            # Filtering rules (strict intersection):
            # - allowed_tools missing/None => allow no tools
            # - allowed_tools == [] => allow no tools
            # - otherwise => allow only tools whose name appears in allowed_tools
            allowed = getattr(primary_agent, "allowed_tools", None)

            if not allowed:
                filtered_function_defs = []
            else:
                # Ensure allowed is a list, preserve order from function_defs
                try:
                    allowed_list = list(allowed)
                except Exception:
                    allowed_list = []

                available_names = [fd.get("name") for fd in function_defs]
                unknown = [n for n in allowed_list if n not in available_names]
                if unknown:
                    logging.warning(
                        "FunctionCallingProcessor: agent '%s' has unknown allowed_tools entries: %s; ignoring",
                        getattr(primary_agent, "name", "<unknown>"),
                        unknown,
                    )

                allowed_set = set([n for n in allowed_list if n in available_names])
                filtered_function_defs = [fd for fd in function_defs if fd.get("name") in allowed_set]

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
    ) -> Generator[str, None, None]:
        """Streaming variant of process_message.

        Same setup as process_message() but calls _run_llm_loop_streaming
        and yields SSE-formatted strings ("data: {json}\n\n").
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

        logging.info(
            "FunctionCallingProcessor(streaming): start account=%s agent=%s session_id=%s context_type=%s max_iterations=%d",
            ctx.account_id,
            ctx.agent_name,
            ctx.conversation_id,
            ctx.context_type,
            ctx.max_iterations,
        )

        final_response_text: Optional[str] = None

        try:
            extra_system_messages = self._get_environment_system_messages()
            if extra_system_messages:
                logging.debug("FunctionCallingProcessor(streaming): injecting %d environment system message(s) from environment_prompt_block", len(extra_system_messages))

            prompt_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=ctx.conversation_id,
                agent_name=ctx.agent_name,
                account_name=ctx.account_id,
                context_type=ctx.context_type,
                max_prompt_chars=6000,
                context_name=ctx.context_name,
                extra_system_messages=extra_system_messages,
            )

            function_defs = self.registry.tools()

            allowed = getattr(primary_agent, "allowed_tools", None)

            if not allowed:
                filtered_function_defs = []
            else:
                try:
                    allowed_list = list(allowed)
                except Exception:
                    allowed_list = []

                available_names = [fd.get("name") for fd in function_defs]
                unknown = [n for n in allowed_list if n not in available_names]
                if unknown:
                    logging.warning(
                        "FunctionCallingProcessor(streaming): agent '%s' has unknown allowed_tools entries: %s; ignoring",
                        getattr(primary_agent, "name", "<unknown>"),
                        unknown,
                    )

                allowed_set = set([n for n in allowed_list if n in available_names])
                filtered_function_defs = [fd for fd in function_defs if fd.get("name") in allowed_set]

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
                # Capture the text content for chat2 storage
                if event.type == "text" and event.content:
                    final_response_text = event.content
                yield event.to_sse()

            # Write chat2 events at stream end (per design decision)
            if ctx.store_this_call and final_response_text:
                self._write_chat2_events(ctx, message, final_response_text)

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
            except Exception:
                logging.exception(
                    "FunctionCallingProcessor(streaming): failed to store error conversation for session_id=%s",
                    ctx.conversation_id,
                )

            yield SSEEvent(type="error", message=error_message).to_sse()
            yield SSEEvent(type="done", conversation_id=ctx.conversation_id).to_sse()

        finally:
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
