# /home/junwin/src/repos/lucy/src/message_processors/function_calling_processor.py

import json
import logging
from typing import List, Optional, Dict, Any

from src.container_config import container
from src.agent_manager import AgentManager
from src.config_manager import ConfigManager
from src.prompt_builders.prompt_builder import PromptBuilder
from src.completion.completion_store import CompletionStore
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.api_helpers import openai_call, ToolResult

from src.handlers.handler_registry import HandlerRegistry


class FunctionCallingProcessor(MessageProcessorInterface):
    def __init__(self):
        self.config = container.get(ConfigManager)
        self.registry = container.get(HandlerRegistry)

    def _safe_json_loads(self, s: str) -> Dict[str, Any]:
        if not s:
            return {}
        try:
            return json.loads(s)
        except Exception:
            logging.warning("Tool arguments were not valid JSON; using empty dict. args=%r", (s or "")[:500])
            return {}

    def _tool_result_to_text(self, tool_result: Any) -> str:
        """
        Tool message content MUST be a string.
        Handlers return a dict; we serialize here (single responsibility).
        """
        if tool_result is None:
            return json.dumps({"ok": False, "error": "Tool returned None"}, ensure_ascii=False)
        if isinstance(tool_result, str):
            return tool_result
        try:
            return json.dumps(tool_result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"ok": False, "error": f"Tool result not JSON serializable: {e}"}, ensure_ascii=False)

    def process_message(
        self,
        agent_name: str,
        account_name: str,
        message: str,
        conversationId: str = "0",
        context_name: str = "",
        second_agent_name: str = "",
        extra_system_messages: Optional[List[str]] = None,
    ) -> str:
        """
        extra_system_messages:
          Optional list of strings to be injected as additional system messages
          (after the agent's primary system prompt, before history/context).
        """
        logging.info("Function Calling Processing message inbound: %s", message)

        agent_manager = container.get(AgentManager)
        agent = agent_manager.get_agent(agent_name)

        model = agent.get("model")
        temperature = agent.get("temperature", 0)
        context_type = agent.get("select_type", "hybrid")

        prompt_builder = PromptBuilder()
        completion_messages = prompt_builder.build_prompt(
            content_text=message,
            conversationId=conversationId,
            agent_name=agent_name,
            account_name=account_name,
            context_type=context_type,
            max_prompt_chars=6000,
            max_prompt_conversations=20,
            context_name=context_name,
            extra_system_messages=extra_system_messages or [],
        )

        # Tools list now comes from the registry (no Quokka)
        function_defs = self.registry.tools()

        max_iterations = 5
        response_text = ""

        store_this_call = bool(agent.get("save_reposnses", False))

        for _ in range(max_iterations):
            result = openai_call(
                messages=completion_messages,
                functions=function_defs,
                temperature=temperature,
                model=model,
                store=store_this_call,
                conversation_id=conversationId,
                session_id=context_name or None,
            )

            # Tool call?
            if isinstance(result, ToolResult) and result.tool_calls:
                if len(result.tool_calls) > 1:
                    logging.warning("Model returned %d tool_calls; only first will be used.", len(result.tool_calls))

                tc0 = result.tool_calls[0]
                tool_call_id = tc0.get("id") or "tool_call_1"
                tool_name = tc0.get("name") or ""
                tool_args_raw = tc0.get("arguments") or "{}"
                tool_args = self._safe_json_loads(tool_args_raw)

                # Execute via registry (no Quokka)
                try:
                    handler = self.registry.create(tool_name, config=self.config)
                except KeyError:
                    tool_result_text = self._tool_result_to_text(
                        {"ok": False, "tool": tool_name, "error": f"Unknown tool: {tool_name}"}
                    )
                else:
                    try:
                        tool_result = handler.execute(tool_args, account_name=account_name)
                        tool_result_text = self._tool_result_to_text(tool_result)
                    except Exception as e:
                        logging.exception("Tool execution failed: %s", tool_name)
                        tool_result_text = self._tool_result_to_text(
                            {"ok": False, "tool": tool_name, "error": f"{type(e).__name__}: {e}"}
                        )


                # Append tool call message (assistant)
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

                # Append tool result message (tool)
                completion_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result_text,
                    }
                )

                continue

            # Final answer
            response_text = (getattr(result, "content", "") or "").strip()

            # Keep this call if you still want context text updates; otherwise remove.
            # (I didn’t import update_context_text_result since you said “get rid of quokka”.)
            # If you still want it:
            # from src.message_processors.message_processor_utils import update_context_text_result
            # update_context_text_result(context_name, response_text, account_name)

            break

        # Save conversation (legacy completion store) if enabled
        if agent.get("save_reposnses", False) and response_text.strip():
            completion_manager_store = container.get(CompletionStore)
            account_completion_manager = completion_manager_store.get_completion_manager(
                agent_name, account_name, agent.get("language_code", "en")[:2]
            )
            account_completion_manager.create_store_completion(conversationId, message, response_text)
            account_completion_manager.save()

        return response_text
