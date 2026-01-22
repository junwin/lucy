from __future__ import annotations
from dataclasses import dataclass
from injector import inject
import logging
from typing import Optional, Dict, Any, List, Iterable
import json
import time

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.handlers.handler_registry import HandlerRegistry
from src.storage.base import Storage
from src.storage.models import ChatMessage
from src.agent import Agent

from src.llm.adapter_interface import LLMAdapter


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
        storage: Storage,
        prompt_builder: PromptBuilderInterface,
        llm_adapter: LLMAdapter,
    ):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.prompt_builder = prompt_builder
        self.llm_adapter = llm_adapter

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
                    tool_result = handler.execute(tool_args, account_name=ctx.account_id)
                    tool_result_text = json.dumps(tool_result, ensure_ascii=False)

                logging.info(
                    "tool_execute_done tool=%s call_id=%s result_preview=%r",
                    tc.name,
                    tc.call_id,
                    (tool_result_text or "")[:200],
                )

                if tc.name == "plan_tasks" and secondary_agent is not None and processor_factory is not None:
                    try:
                        maybe = json.loads(tool_result_text or "{}")
                    except Exception:
                        maybe = {}

                    if isinstance(maybe, dict) and maybe.get("ok") and maybe.get("kind") == "tasklist":
                        logging.info(
                            "FunctionCallingProcessor: executing tasklist from plan_tasks using supervisor=%s worker=%s session_id=%s call_id=%s",
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
            prompt_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=ctx.conversation_id,
                agent_name=ctx.agent_name,
                account_name=ctx.account_id,
                context_type=ctx.context_type,
                max_prompt_chars=6000,
                context_name=ctx.context_name,
                extra_system_messages=[],
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
                self.storage.append_chat_message(
                    ctx.conversation_id,
                    ChatMessage(role="user", content=message, metadata={"agent": ctx.agent_name}),
                )
                self.storage.append_chat_message(
                    ctx.conversation_id,
                    ChatMessage(role="assistant", content=response_text, metadata={"agent": ctx.agent_name}),
                )

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
                self.storage.append_chat_message(
                    ctx.conversation_id,
                    ChatMessage(role="user", content=message, metadata={"agent": ctx.agent_name}),
                )
                self.storage.append_chat_message(
                    ctx.conversation_id,
                    ChatMessage(
                        role="assistant",
                        content=error_message + f" (Details: {type(e).__name__})",
                        metadata={"agent": ctx.agent_name, "error": True},
                    ),
                )
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
