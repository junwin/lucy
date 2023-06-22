import openai
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
        response = ""
        agent_manager = container.get(AgentManager)
        agent = agent_manager.get_agent(agent_name)
        model = agent["model"]
        temperature = agent["temperature"]
        context_type = agent["select_type"]

        function_calling_definition = self.handler.get_function_calling_definition()

        completion_messages = [{"role": "user", "content": message}]
        response_message = get_completionWithFunctions(completion_messages, function_calling_definition)

        if response_message.get("function_call"):
            action = []
            function_name = response_message["function_call"]["name"]
            # function_to_call = available_functions[function_name]
            function_args_text = response_message["function_call"]["arguments"]
            function_args = json.loads(function_args_text)
            action = [{"action_name": function_name}]
            for key, value in function_args.items():
                action.append({key: value})

            action_dict = dict()
            action_dict["action_name"] = function_name
            for key, value in function_args.items():
                action_dict[key] = value

            response = self.handler.process_action_dict(action_dict, account_name)
            response_message_text = QuokkaLoki.handler_repsonse_formated_text(response)

            completion_messages.append(response_message)
            completion_messages.append(
                {
                    "role": "function",
                    "name": function_name,
                    "content": response_message_text,
                }
            )
            response_message2 = get_completionWithFunctions(completion_messages, function_calling_definition)

            return response_message2["content"]
        
        return response_message["content"]
    

    def is_none_or_empty(self, string):
        return string is None or string.strip() == ""
