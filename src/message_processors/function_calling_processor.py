import logging
import re
import json
from injector import Injector

from src.container_config import container
from src.config_manager import ConfigManager
from src.response_handler import FileResponseHandler
from src.source_code_response_handler import SourceCodeResponseHandler
from src.agent_manager import AgentManager
from src.message_processors.message_preProcess import MessagePreProcess
from src.api_helpers import ask_question, get_completion, get_completionWithFunctions
from src.message_processors.message_processor_interface import MessageProcessorInterface

from src.prompt_builders.prompt_builder import PromptBuilder
# from src.completion.completion_manager import CompletionManager
from src.completion.completion_store import CompletionStore
from src.handlers.quokka_loki import QuokkaLoki
from src.handlers.task_update_handler import TaskUpdateHandler
from src.handlers.file_save_handler import FileSaveHandler
from src.handlers.command_execution_handler import CommandExecutionHandler
from src.handlers.user_action_required_handler import UserActionRequiredHandler
from src.handlers.file_load_handler import FileLoadHandler
from src.handlers.web_search_handler import WebSearchHandler
from src.handlers.scrape_web_page_handler import ScrapeWebPage

from src.message_processors.message_processor_utils import setup_action_dict, post_process_quokka_loki_action_dict, update_context_text_result


class FunctionCallingProcessor(MessageProcessorInterface):
    def __init__(self):
        # self.name = name
        agent_manager = container.get(AgentManager)
        self.config = container.get(ConfigManager)
        prompt_base_path = self.config.get('prompt_base_path')
        self.seed_conversations = []
        self.handler = QuokkaLoki()
        # self.node_manager = container.get(NodeManager)
        # task_update_handler = TaskUpdateHandler(self.node_manager)
        file_save_handler = FileSaveHandler()
        command_execution_handler = CommandExecutionHandler()
        user_action_required_handler = UserActionRequiredHandler()
        file_load_handler = FileLoadHandler()
        self.handler.add_handler(file_save_handler)
        self.handler.add_handler(command_execution_handler)
        # self.handler.add_handler(user_action_required_handler)
        self.handler.add_handler(file_load_handler)
        # self.handler.add_handler(task_update_handler)
        web_search_handler = WebSearchHandler()
        self.handler.add_handler(web_search_handler)
        scrape_web_page_handler = ScrapeWebPage()
        self.handler.add_handler(scrape_web_page_handler)



    def process_message(self, agent_name: str, account_name: str, message: str, conversationId="0", context_name='', second_agent_name='') -> str:
        logging.info(f'Function Calling Processing message inbound: {message}')
        response_text = ""
        agent_manager = container.get(AgentManager)
        agent = agent_manager.get_agent(agent_name)
        model = agent["model"]
        temperature = agent["temperature"]
        context_type = agent["select_type"]

        prompt_builder = PromptBuilder()
        completion_messages = prompt_builder.build_prompt(
            message,
            conversationId,
            agent_name,
            account_name,
            context_type,
            6000,
            20,
            context_name,
        )

        function_calling_definition = self.handler.get_function_calling_definition()

        max_iterations = 5
        response_message = {"content": ""}  # fallback default

        for _ in range(max_iterations):
            # Call OpenAI with tools
            response_message = get_completionWithFunctions(
                completion_messages,
                function_calling_definition,
                temperature,
                model,
            )

            # Did the model request a function/tool?
            if response_message.get("function_call"):
                # Extract params
                action_dict = setup_action_dict(response_message)

                # Execute our local handler(s)
                tool_result_text = post_process_quokka_loki_action_dict(
                    action_dict, account_name, context_name
                )

                # Wire up tool calling messages in the new format
                tool_call_id = response_message.get("tool_call_id", "tool_call_1")

                # 1) assistant message with tool_calls
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
                                    "arguments": response_message["function_call"]["arguments"],
                                },
                            }
                        ],
                    }
                )

                # 2) tool message with the result
                completion_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": tool_result_text,
                    }
                )

                # Loop again so the model can see the tool result
                continue

            else:
                # No more tool calls – we have the final assistant answer
                response_text = response_message.get("content", "")
                update_context_text_result(context_name, response_text, account_name)
                break

        # Save conversation to completion store if configured
        if agent.get('save_reposnses', False):
            if not self.is_none_or_empty(response_text):
                completion_manager_store = container.get(CompletionStore)
                account_completion_manager = completion_manager_store.get_completion_manager(
                    agent_name, account_name, agent['language_code'][:2]
                )
                account_completion_manager.create_store_completion(
                    conversationId, message, response_text
                )
                account_completion_manager.save()

        return response_text

    
 
    def is_none_or_empty(self, string):
        return string is None or string.strip() == ""
