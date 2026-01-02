# /home/junwin/src/repos/lucy/src/message_processors/function_calling_processor.py

from injector import inject
import logging
from typing import Optional, Dict, Any, List
import json

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
            return json.loads(s)
        except Exception:
            logging.warning(
                "Tool arguments were not valid JSON; using empty dict. args=%r",
                (s or "")[:500],
            )
            return {}

    def _tool_result_to_text(self, tool_result: Any) -> str:
        """Tool message content MUST be a string. Handlers return a dict; we serialize here.

        Also enforces a maximum size based on config["max_tool_result_chars"].
        """
        if tool_result is None:
            s = json.dumps({"ok": False, "error": "Tool returned None"}, ensure_ascii=False)
        elif isinstance(tool_result, str):
            s = tool_result
        else:
            try:
                s = json.dumps(tool_result, ensure_ascii=False)
            except Exception as e:
                s = json.dumps(
                    {"ok": False, "error": f"Tool result not JSON serializable: {e}"},
                    ensure_ascii=False,
                )

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
        """Execute a simple sequential tasklist (unchanged from your version, lightly tightened)."""

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

        summary = {"ok": all(r.get("ok") for r in results) if results else False, "description": tasklist_description, "tasks": results}

        logging.info(
            "_execute_simple_tasklist: completed supervisor=%s worker=%s session_id=%s tasks=%d ok=%s",
            supervisor_agent.name,
            worker_agent.name if worker_agent else None,
            conversation_id,
            len(results),
            summary["ok"],
        )
        return summary

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
        logging.info("FunctionCallingProcessor inbound message: %s", message)

        if not primary_agent:
            return "[FunctionCallingProcessor] Missing primary_agent configuration."

        account_id = (account.get("accountId") or "").strip()
        if not account_id:
            return "[FunctionCallingProcessor] Missing account.accountId."

        agent_name = primary_agent.name or "unknown"
        model = primary_agent.model
        temperature = primary_agent.temperature
        context_type = primary_agent.context_type or "hybrid"

        max_iterations = int(primary_agent.max_function_call_iterations or 10)
        if max_iterations <= 0:
            logging.warning("max_function_call_iterations for agent '%s' is %d; using 1 instead", agent_name, max_iterations)
            max_iterations = 1

        logging.info(
            "FunctionCallingProcessor: start account=%s agent=%s session_id=%s context_type=%s max_iterations=%d",
            account_id,
            agent_name,
            conversation_id,
            context_type,
            max_iterations,
        )

        try:
            prompt_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=conversation_id,
                agent_name=agent_name,
                account_name=account_id,
                context_type=context_type,
                max_prompt_chars=6000,
                context_name=context_name,
                extra_system_messages=[],
            )

            function_defs = self.registry.tools()
            store_this_call = bool(primary_agent.save_responses)
            delegation_depth = int(getattr(primary_agent, "delegation_depth", 0))

            response_text = ""
            previous_response_id: Optional[str] = None

            # For OpenAI Responses: input can be either:
            #  - list of role/content messages (initial turn)
            #  - list of function_call_output items (continuation turns)
            next_input_items: List[Dict[str, Any]] = prompt_messages

            for iteration in range(1, max_iterations + 1):
                llm_response = self.llm_adapter.call_model(
                    model=model,
                    input=next_input_items,
                    temperature=temperature,
                    tools=function_defs,
                    tool_choice="auto" if function_defs else None,
                    store=store_this_call,
                    metadata={"conversation_id": conversation_id, "session_id": context_name or None},
                    previous_response_id=previous_response_id,
                )

                # Always carry forward the response_id for chaining
                result_response_id = self.llm_adapter.get_response_id(llm_response)
                if result_response_id:
                    previous_response_id = result_response_id

                logging.info(
                    "FunctionCallingProcessor: iteration=%d/%d agent=%s session_id=%s response_id=%s",
                    iteration,
                    max_iterations,
                    agent_name,
                    conversation_id,
                    previous_response_id,
                )

                tool_calls = self.llm_adapter.extract_tool_calls(llm_response)

                # Tool-call path
                if tool_calls:
                    if not previous_response_id:
                        raise ToolHandlerError(
                            "LLM returned tool_calls but no response_id. "
                            "Cannot chain function_call_output. Ensure the LLMApi propagates response_id."
                        )

                    tool_output_items: List[Dict[str, Any]] = []

                    logging.info(
                        "FunctionCallingProcessor: tool_call iteration=%d/%d agent=%s session_id=%s tool_count=%d prev_response_id=%s",
                        iteration,
                        max_iterations,
                        agent_name,
                        conversation_id,
                        len(tool_calls),
                        previous_response_id,
                    )

                    for idx, tc in enumerate(tool_calls):
                        tool_name = tc.get("name") or ""
                        tool_call_id = tc.get("id")

                        if not tool_call_id:
                            raise ToolHandlerError(
                                f"Tool call missing id/call_id for tool '{tool_name}'. Cannot send function_call_output."
                            )

                        tool_args_raw = tc.get("arguments") or "{}"
                        tool_args = self._safe_json_loads(tool_args_raw)

                        try:
                            handler = self.registry.create(tool_name, config=self.config)
                            tool_result = handler.execute(tool_args, account_name=account_id)

                            # Tool-level failure is NOT fatal: pass it back to the model so it can recover.
                            if isinstance(tool_result, dict) and tool_result.get("ok") is False:
                                error_text = tool_result.get("error") or "Unknown tool error"
                                logging.warning(
                                    "FunctionCallingProcessor: tool '%s' returned ok=False: %s",
                                    tool_name,
                                    error_text,
                                )

                            # plan_tasks delegation hook
                            if (
                                tool_name == "plan_tasks"
                                and isinstance(tool_result, Dict)
                                and tool_result.get("ok")
                                and tool_result.get("kind") == "tasklist"
                                and secondary_agent is not None
                                and processor_factory is not None
                            ):
                                logging.info(
                                    "FunctionCallingProcessor: executing tasklist from plan_tasks using supervisor=%s worker=%s session_id=%s",
                                    agent_name,
                                    secondary_agent.name,
                                    conversation_id,
                                )
                                tool_result = self._execute_simple_tasklist(
                                    tasklist=tool_result,
                                    supervisor_agent=primary_agent,
                                    worker_agent=secondary_agent,
                                    account=account,
                                    conversation_id=conversation_id,
                                    context_name=context_name,
                                    processor_factory=processor_factory,
                                    delegation_depth=delegation_depth,
                                )

                            tool_result_text = self._tool_result_to_text(tool_result)

                        except ToolResultTooLargeError as e:
                            tool_result_text = self._tool_result_to_text({"ok": False, "tool": tool_name, "error": str(e)})
                        except Exception as e:
                            logging.exception("Tool execution failed: %s", tool_name)
                            raise ToolHandlerError(f"{type(e).__name__}: {e}")

                        tool_output_items.append(
                            self.llm_adapter.format_tool_output(call_id=str(tool_call_id), output=tool_result_text)
                        )

                    logging.info(
                        "FunctionCallingProcessor: sending %d function_call_output items chained to response_id=%s call_ids=%s",
                        len(tool_output_items),
                        previous_response_id,
                        [x.get("call_id") for x in tool_output_items],
                    )

                    # Next iteration: ONLY tool outputs; chain via previous_response_id
                    next_input_items = tool_output_items

                    if iteration >= max_iterations:
                        logging.error(
                            "FunctionCallingProcessor: exceeded max_function_call_iterations=%d for agent '%s' in conversation_id=%s",
                            max_iterations,
                            agent_name,
                            conversation_id,
                        )
                        response_text = (
                            "I ran into an internal limit while trying to call tools multiple times. "
                            "I may not have completed all requested actions. Please try rephrasing or splitting your request."
                        )
                        break

                    continue

                # Normal response (no tool calls)
                response_text = self.llm_adapter.get_text(llm_response)
                break

            # Persist conversation if enabled
            if store_this_call and response_text:
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(role="user", content=message, metadata={"agent": agent_name}),
                )
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(role="assistant", content=response_text, metadata={"agent": agent_name}),
                )

            logging.info(
                "FunctionCallingProcessor: completed agent=%s session_id=%s iterations=%d response_preview=%r",
                agent_name,
                conversation_id,
                iteration,
                (response_text or "")[:80],
            )
            return response_text

        except ToolHandlerError:
            raise

        except Exception as e:
            logging.exception("FunctionCallingProcessor: unhandled error agent=%s session_id=%s", agent_name, conversation_id)

            error_message = "I ran into an internal error while processing your request. The issue has been logged."

            # Best-effort store
            try:
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(role="user", content=message, metadata={"agent": agent_name}),
                )
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(
                        role="assistant",
                        content=error_message + f" (Details: {type(e).__name__})",
                        metadata={"agent": agent_name, "error": True},
                    ),
                )
            except Exception:
                logging.exception("FunctionCallingProcessor: failed to store error conversation for session_id=%s", conversation_id)

            raise
