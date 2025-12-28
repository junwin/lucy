from injector import inject
import logging
from typing import Optional, Dict, Any
import json
from src.config_manager import ConfigManager
#from src.prompt_builders.prompt_builder import PromptBuilder
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
    def __init__(self, config: ConfigManager, registry: HandlerRegistry, storage: Storage, prompt_builder: PromptBuilderInterface,):
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

        # Build prompt
        # prompt_builder = PromptBuilder()
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

        max_iterations = 5
        response_text = ""

        store_this_call = bool(primary_agent.get("save_reposnses", False))

        for _ in range(max_iterations):
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
                            {"ok": False, "tool": tool_name, "error": f"{type(e).__name__}: {e}"}
                        )

                    completion_messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {"name": tool_name, "arguments": tool_args_raw},
                                }
                            ],
                        }
                    )
                    completion_messages.append(
                        {"role": "tool", "tool_call_id": tool_call_id, "content": tool_result_text}
                    )
                continue

            response_text = (getattr(result, "content", "") or "").strip()
            break

        if store_this_call and response_text:
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(role="user", content=message, metadata={"agent": agent_name}),
            )
            self.storage.append_chat_message(
                conversation_id,
                ChatMessage(role="assistant", content=response_text, metadata={"agent": agent_name}),
            )

        return response_text
