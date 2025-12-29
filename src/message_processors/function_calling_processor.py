from injector import inject
import logging
from typing import Optional, Dict, Any
import json
import sys

from src.config_manager import ConfigManager
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.prompt_builders.prompt_builder_interface import PromptBuilderInterface
from src.message_processors.types import AgentDict, AccountDict
from src.api_helpers import openai_call, ToolResult
from src.handlers.handler_registry import HandlerRegistry
from src.storage.base import Storage
from src.storage.models import ChatMessage


class ToolResultTooLargeError(Exception):
    """Raised when a tool result exceeds the configured max_tool_result_chars."""


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

    def _store_error_conversation(
        self,
        *,
        conversation_id: str,
        agent_name: str,
        user_message: str,
        error_message: str,
    ) -> None:
        """Append the inbound user message and an assistant error message to storage.

        This is best-effort: any storage error is logged but does not raise further.
        """
        try:
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(
                    role="user",
                    content=user_message,
                    metadata={"agent": agent_name},
                ),
            )
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(
                    role="assistant",
                    content=error_message,
                    metadata={"agent": agent_name, "error": True},
                ),
            )
        except Exception:
            logging.exception(
                "FunctionCallingProcessor: failed to store error conversation for session_id=%s",
                conversation_id,
            )

    def process_message(
        self,
        *,
        primary_agent: AgentDict,
        account: AccountDict,
        message: str,
        conversation_id: str = "0",
        context_name: str = "",
        secondary_agent: Optional[AgentDict] = None,
        processor_factory: Optional[Any] = None,
    ) -> str:
        logging.info("FunctionCallingProcessor inbound message: %s", message)

        if not primary_agent:
            return "[FunctionCallingProcessor] Missing primary_agent configuration."

        account_id = (account.get("accountId") or "").strip()
        if not account_id:
            return "[FunctionCallingProcessor] Missing account.accountId."

        agent_name = (primary_agent.get("name") or "").strip() or "unknown"
        model = primary_agent.get("model")
        temperature = primary_agent.get("temperature", 0)
        context_type = primary_agent.get("select_type", "hybrid")

        # Per-agent max function call iterations (fallback to 10)
        max_iterations = int(primary_agent.get("max_function_call_iterations", 10))
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
            # Build prompt
            completion_messages = self.prompt_builder.build_prompt(
                content_text=message,
                conversation_id=conversation_id,
                agent_name=agent_name,
                account_name=account_id,
                context_type=context_type,
                max_prompt_chars=6000,
                max_prompt_conversations=20,
                context_name=context_name,
                extra_system_messages=[],  # wire this back later if you want
            )

            function_defs = self.registry.tools()

            response_text = ""

            store_this_call = bool(primary_agent.get("save_reposnses", False))

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
                            tool_result_text = self._tool_result_to_text(tool_result)
                        except ToolResultTooLargeError as e:
                            tool_result_text = self._tool_result_to_text(
                                {"ok": False, "tool": tool_name, "error": str(e)}
                            )
                        except Exception as e:
                            logging.exception("Tool execution failed: %s", tool_name)
                            tool_result_text = self._tool_result_to_text(
                                {
                                    "ok": False,
                                    "tool": tool_name,
                                    "error": f"{type(e).__name__}: {e}",
                                }
                            )

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
                "The issue has been logged and the process will now exit."
            )

            # Best-effort: store the inbound message and error as a conversation
            self._store_error_conversation(
                conversation_id=conversation_id,
                agent_name=agent_name,
                user_message=message,
                error_message=error_message + f" (Details: {type(e).__name__})",
            )

            # Exit the process as requested
            try:
                sys.exit(1)
            except SystemExit:
                # Re-raise to ensure the caller does not continue
                raise

            # Fallback return (should not be reached, but keeps type checkers happy)
            return error_message
