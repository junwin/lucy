from injector import inject
import logging
from typing import Optional, Dict, Any
import json

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.api_helpers import openai_call, ToolResult
from src.handlers.handler_registry import HandlerRegistry
from src.storage.base import Storage
from src.storage.models import ChatMessage
from src.agent import Agent


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
    ):
        self.config = config
        self.registry = registry
        self.storage = storage
        self.context_type = ""
        self.prompt_builder = prompt_builder

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
        # Serialize first
        if tool_result is None:
            s = json.dumps(
                {"ok": False, "error": "Tool returned None"},
                ensure_ascii=False,
            )
        elif isinstance(tool_result, str):
            s = tool_result
        else:
            try:
                s = json.dumps(tool_result, ensure_ascii=False)
            except Exception as e:
                s = json.dumps(
                    {
                        "ok": False,
                        "error": f"Tool result not JSON serializable: {e}",
                    },
                    ensure_ascii=False,
                )

        # Enforce size limit from config (fallback to 20000 if missing)
        max_chars = int(self.config.get("max_tool_result_chars", 20000))
        if len(s) > max_chars:
            # Log a small sample of the oversized output for debugging
            logging.error(
                "Tool result too large: %d chars (limit %d). Sample: %r",
                len(s),
                max_chars,
                s[:1000],
            )
            raise ToolResultTooLargeError(
                f"Tool result too large: {len(s)} chars (limit {max_chars})"
            )

        return s

    # ------------------------------------------------------------------
    # Simple tasklist execution (sequential tasks, no map yet)
    # ------------------------------------------------------------------

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
        """Execute a simple sequential tasklist.

        Expected tasklist shape (minimal):
        {
          "kind": "tasklist",
          "description": "...",
          "tasks": [
            {
              "id": "task-1",
              "type": "task",
              "title": "...",
              "agent": "lucy" | "colin",
              "instruction": "...",
              "file": "...",          # optional
              "params": { ... }        # optional
            },
            ...
          ]
        }

        - No dependency graph yet: tasks are executed in order.
        - If task.agent == worker_agent.name, we run it with the worker agent.
        - Results are collected into a list and returned as a dict suitable for
          use as a tool result.
        """

        # For now, delegation depth is controlled by a config value on the supervisor
        max_depth = int(getattr(supervisor_agent, "max_delegation_depth", 1))
        if delegation_depth >= max_depth:
            logging.warning(
                "_execute_simple_tasklist: delegation depth %d >= max %d for agent=%s "
                "session_id=%s; refusing to delegate further.",
                delegation_depth,
                max_depth,
                supervisor_agent.name,
                conversation_id,
            )
            return {
                "ok": False,
                "error": "Max delegation depth exceeded while executing the tasklist.",
            }

        tasks = tasklist.get("tasks") or []
        if not isinstance(tasks, list):
            return {"ok": False, "error": "tasklist.tasks must be a list."}

        results = []
        tasklist_description = tasklist.get("description") or ""

        logging.info(
            "_execute_simple_tasklist: start supervisor=%s worker=%s session_id=%s "
            "tasks=%d depth=%d/%d description=%r",
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
                logging.warning(
                    "_execute_simple_tasklist: unsupported task type=%s in id=%s; skipping.",
                    task_type,
                    task_id,
                )
                results.append(
                    {
                        "id": task_id,
                        "ok": False,
                        "error": f"Unsupported task type: {task_type}",
                    }
                )
                continue

            if not instruction:
                logging.warning(
                    "_execute_simple_tasklist: task id=%s has no instruction; skipping.",
                    task_id,
                )
                results.append(
                    {
                        "id": task_id,
                        "ok": False,
                        "error": "Task has no instruction to execute.",
                    }
                )
                continue

            # Build the message for the agent
            msg_parts = [instruction]
            if file_path:
                msg_parts.append(f"\n\nFocus file: {file_path}")
            task_message = "".join(msg_parts)

            if worker_agent and task_agent_name == worker_agent.name:
                # Run with worker agent via this processor (or a new one via factory if needed)
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
                    results.append(
                        {
                            "id": task_id,
                            "ok": True,
                            "agent": task_agent_name,
                            "response": task_response,
                        }
                    )
                except ToolHandlerError as e:
                    logging.exception(
                        "_execute_simple_tasklist: error executing worker task id=%s",
                        task_id,
                    )
                    results.append(
                        {
                            "id": task_id,
                            "ok": False,
                            "agent": task_agent_name,
                            "error": f"{type(e).__name__}: {e}",
                        }
                    )
                    break

            else:
                logging.warning(
                    "_execute_simple_tasklist: unknown agent=%s for task id=%s; skipping.",
                    task_agent_name,
                    task_id,
                )
                results.append(
                    {
                        "id": task_id,
                        "ok": False,
                        "agent": task_agent_name,
                        "error": f"Unknown agent: {task_agent_name}",
                    }
                )
                continue

        summary = {
            "ok": all(r.get("ok") for r in results) if results else False,
            "description": tasklist_description,
            "tasks": results,
        }

        logging.info(
            "_execute_simple_tasklist: completed supervisor=%s worker=%s session_id=%s "
            "tasks=%d ok=%s",
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

        # Per-agent max function call iterations (fallback to 10)
        max_iterations = int(primary_agent.max_function_call_iterations or 10)
        if max_iterations <= 0:
            logging.warning(
                "max_function_call_iterations for agent '%s' is %d; using 1 instead",
                agent_name,
                max_iterations,
            )
            max_iterations = 1

        logging.info(
            "FunctionCallingProcessor: start account=%s agent=%s session_id=%s "
            "context_type=%s max_iterations=%d",
            account_id,
            agent_name,
            conversation_id,
            context_type,
            max_iterations,
        )

        try:
            # Build prompt (PromptBuilder now uses agent.max_prompt_conversations internally)
            completion_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=conversation_id,
                agent_name=agent_name,
                account_name=account_id,
                context_type=context_type,
                max_prompt_chars=6000,
                context_name=context_name,
                extra_system_messages=[],  # wire this back later if you want
            )

            function_defs = self.registry.tools()

            response_text = ""

            store_this_call = bool(primary_agent.save_responses)

            # Delegation depth for tasklist execution (default 0 if not provided)
            delegation_depth = int(getattr(primary_agent, "delegation_depth", 0))

            for iteration in range(1, max_iterations + 1):
                result = openai_call(
                    messages=completion_messages,
                    functions=function_defs,
                    temperature=temperature,
                    model=model,
                    store=store_this_call,
                    conversation_id=conversation_id,
                    session_id=context_name or None,
                )

                if isinstance(result, ToolResult) and result.tool_calls:
                    logging.info(
                        "FunctionCallingProcessor: tool_call iteration=%d/%d agent=%s "
                        "session_id=%s tool_count=%d",
                        iteration,
                        max_iterations,
                        agent_name,
                        conversation_id,
                        len(result.tool_calls),
                    )

                    for idx, tc in enumerate(result.tool_calls):
                        tool_call_id = tc.get("id") or f"tool_call_{idx+1}"
                        tool_name = tc.get("name") or ""
                        tool_args_raw = tc.get("arguments") or "{}"
                        tool_args = self._safe_json_loads(tool_args_raw)

                        try:
                            handler = self.registry.create(tool_name, config=self.config)
                            tool_result = handler.execute(tool_args, account_name=account_id)

                            # If the handler reports failure via ok=False, treat as a
                            # terminal tool error for this request.
                            if isinstance(tool_result, dict) and tool_result.get("ok") is False:
                                error_text = tool_result.get("error") or "Unknown tool error"
                                logging.error(
                                    "FunctionCallingProcessor: tool '%s' reported failure: %s",
                                    tool_name,
                                    error_text,
                                )
                                raise ToolHandlerError(
                                    f"Tool '{tool_name}' failed: {error_text}"
                                )

                            # If this is a plan_tasks result, and we have a secondary agent,
                            # execute the tasklist using the simple tasklist executor.
                            if (
                                tool_name == "plan_tasks"
                                and isinstance(tool_result, Dict)
                                and tool_result.get("ok")
                                and tool_result.get("kind") == "tasklist"
                                and secondary_agent is not None
                                and processor_factory is not None
                            ):
                                logging.info(
                                    "FunctionCallingProcessor: executing tasklist from plan_tasks "
                                    "using supervisor=%s worker=%s session_id=%s",
                                    agent_name,
                                    secondary_agent.name,
                                    conversation_id,
                                )
                                tasklist_summary = self._execute_simple_tasklist(
                                    tasklist=tool_result,
                                    supervisor_agent=primary_agent,
                                    worker_agent=secondary_agent,
                                    account=account,
                                    conversation_id=conversation_id,
                                    context_name=context_name,
                                    processor_factory=processor_factory,
                                    delegation_depth=delegation_depth,
                                )
                                tool_result = tasklist_summary

                            tool_result_text = self._tool_result_to_text(tool_result)
                        except ToolResultTooLargeError as e:
                            tool_result_text = self._tool_result_to_text(
                                {"ok": False, "tool": tool_name, "error": str(e)}
                            )
                        except Exception as e:
                            logging.exception("Tool execution failed: %s", tool_name)
                            raise ToolHandlerError(f"{type(e).__name__}: {e}")

                        completion_messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": tool_call_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_name,
                                            "arguments": tool_args_raw,
                                        },
                                    }
                                ],
                            }
                        )
                        completion_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": tool_result_text,
                            }
                        )

                    # If we've hit the max iterations after processing tool calls, stop
                    if iteration >= max_iterations:
                        logging.error(
                            "FunctionCallingProcessor: exceeded max_function_call_iterations=%d "
                            "for agent '%s' in conversation_id=%s",
                            max_iterations,
                            agent_name,
                            conversation_id,
                        )
                        response_text = (
                            "I ran into an internal limit while trying to call tools multiple times. "
                            "I may not have completed all requested actions. Please try rephrasing or "
                            "splitting your request into smaller steps."
                        )
                        break

                    # Otherwise, continue the loop to let the model see tool results
                    continue

                # No tool calls: we have a normal assistant response
                response_text = (getattr(result, "content", "") or "").strip()
                break

            if store_this_call and response_text:
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(
                        role="user",
                        content=message,
                        metadata={"agent": agent_name},
                    ),
                )
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(
                        role="assistant",
                        content=response_text,
                        metadata={"agent": agent_name},
                    ),
                )

            logging.info(
                "FunctionCallingProcessor: completed agent=%s session_id=%s "
                "iterations=%d response_preview=%r",
                agent_name,
                conversation_id,
                iteration,
                (response_text or "")[:80],
            )

            return response_text

        except ToolHandlerError:
            # Let ToolHandlerError propagate to the caller (e.g. AskRequestHandler)
            raise
        except Exception as e:
            # Log full stack trace with context
            logging.exception(
                "FunctionCallingProcessor: unhandled error agent=%s session_id=%s",
                agent_name,
                conversation_id,
            )

            # Build a user-facing error message
            error_message = (
                "I ran into an internal error while processing your request. "
                "The issue has been logged."
            )

            # Best-effort: store the inbound message and error as a conversation
            try:
                self.storage.append_chat_message(
                    conversation_id,
                    ChatMessage(
                        role="user",
                        content=message,
                        metadata={"agent": agent_name},
                    ),
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
                logging.exception(
                    "FunctionCallingProcessor: failed to store error conversation for session_id=%s",
                    conversation_id,
                )

            # Re-raise so the HTTP layer can return an error response
            raise
