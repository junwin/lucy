import logging
from typing import List, Optional

from src.container_config import container
from src.agent_manager import AgentManager
from src.config_manager import ConfigManager
from src.prompt_builders.prompt_builder import PromptBuilder
from src.completion.completion_store import CompletionStore
from src.handlers.quokka_loki import QuokkaLoki
from src.handlers.file_save_handler import FileSaveHandler
from src.handlers.command_execution_handler import CommandExecutionHandler
from src.handlers.user_action_required_handler import UserActionRequiredHandler
from src.handlers.file_load_handler import FileLoadHandler
from src.handlers.web_search_handler import WebSearchHandler
from src.handlers.scrape_web_page_handler import ScrapeWebPage
from src.message_processors.message_processor_interface import MessageProcessorInterface
from src.api_helpers import get_completion_with_tools
from src.message_processors.message_processor_utils import (
    setup_action_dict,
    post_process_quokka_loki_action_dict,
    update_context_text_result,
)


class FunctionCallingProcessor(MessageProcessorInterface):
    def __init__(self):
        self.config = container.get(ConfigManager)
        self.handler = QuokkaLoki()

        # Register handlers (tools)
        self.handler.add_handler(FileSaveHandler())
        self.handler.add_handler(CommandExecutionHandler())
        # self.handler.add_handler(UserActionRequiredHandler())  # intentionally disabled
        self.handler.add_handler(FileLoadHandler())
        self.handler.add_handler(WebSearchHandler())
        self.handler.add_handler(ScrapeWebPage())

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
          Used by guided-conversation style processors to inject SME guidance.
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

        function_defs = self.handler.get_function_calling_definition()

        max_iterations = 5
        response_text = ""

        for _ in range(max_iterations):
            response_message = get_completion_with_tools(
                messages=completion_messages,
                functions=function_defs,
                temperature=temperature,
                model=model,
            )

            # Tool call?
            if response_message.get("function_call"):
                action_dict = setup_action_dict(response_message)
                tool_result_text = post_process_quokka_loki_action_dict(
                    action_dict, account_name, context_name
                )

                tool_call_id = response_message.get("tool_call_id", "tool_call_1")

                completion_messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": action_dict["action_name"],
                                    "arguments": response_message["function_call"].get("arguments", "{}"),
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

                continue

            # Final answer
            response_text = response_message.get("content", "") or ""
            update_context_text_result(context_name, response_text, account_name)
            break

        # Save conversation (legacy completion store) if enabled
        if agent.get("save_reposnses", False) and response_text.strip():
            completion_manager_store = container.get(CompletionStore)
            account_completion_manager = completion_manager_store.get_completion_manager(
                agent_name, account_name, agent.get("language_code", "en")[:2]
            )
            account_completion_manager.create_store_completion(
                conversationId, message, response_text
            )
            account_completion_manager.save()

        return response_text