import logging
import json
from src.context.context import Context
from src.context.context_manager import ContextManager
from src.completion.completion_store import CompletionStore
from src.handlers.quokka_loki import QuokkaLoki
from src.handlers.task_update_handler import TaskUpdateHandler
from src.handlers.file_save_handler import FileSaveHandler
from src.handlers.command_execution_handler import CommandExecutionHandler
from src.handlers.user_action_required_handler import UserActionRequiredHandler
from src.handlers.file_load_handler import FileLoadHandler
from src.handlers.web_search_handler import WebSearchHandler
from src.handlers.scrape_web_page_handler import ScrapeWebPage
from src.config_manager import ConfigManager

config = ConfigManager('config.json')

def post_process_quokka_loki_response(response: str, account_name:str, context_name: str) -> str:
    handler = QuokkaLoki()
    handler = setup_quokka_loki_handlers(handler, account_name)
    handler.account_name = account_name
    rh_repsonse = handler.process_request(response)
    response_text = QuokkaLoki.handler_repsonse_formated_text(rh_repsonse)
    if response_text != '':
        response = response + " response: " + response_text
        if context_name != "" and context_name != "none":
            context_mgr =ContextManager(config)
            context = context_mgr.get_context(account_name, context_name)
            context.update_from_results(rh_repsonse)
            context_mgr.post_context(context)

def post_process_quokka_loki_action_dict(action_dict: dict, account_name:str, context_name: str) -> str:
    handler = QuokkaLoki()
    handler = setup_quokka_loki_handlers(handler, account_name)
    handler.account_name = account_name
    rh_repsonse = handler.process_action_dict(action_dict, account_name)
    response_text = QuokkaLoki.handler_repsonse_formated_text(rh_repsonse)
    if response_text != '':
        if context_name != "" and context_name != "none":
            context_mgr =ContextManager(config)
            context = context_mgr.get_context(account_name, context_name)
            context.update_from_results(rh_repsonse)
            context_mgr.post_context(context)
    return response_text

def update_context_text_result(context_name:str, result_text:str, account_name:str) -> None:
    if result_text != '':
        if context_name != "" and context_name != "none":
            context_mgr =ContextManager(config)
            context = context_mgr.get_context(account_name, context_name)
            context.add_action("last step result", result_text, "step result")
            context_mgr.post_context(context)


def setup_action_dict(response_message) -> dict:
    function_name = response_message["function_call"]["name"]
    function_args_text = response_message["function_call"]["arguments"]
    
    try:
        # Attempt to parse the JSON arguments
        function_args = json.loads(function_args_text)
    except json.JSONDecodeError as e:
        # Log the error and the problematic JSON text
        logging.error(f"Failed to parse JSON: {e} - JSON text: {function_args_text}")
        # Default to an empty dictionary if parsing fails
        function_args = {}

    # Extract the parameters and name of the function requested
    action_dict = dict()
    action_dict["action_name"] = function_name
    for key, value in function_args.items():
        action_dict[key] = value

    return action_dict

def setup_quokka_loki_handlers(handler: QuokkaLoki, account_name: str) -> None:
    handler.account_name = account_name
    
    handlers = [
        #TaskUpdateHandler(),
        FileSaveHandler(),
        CommandExecutionHandler(),
        #UserActionRequiredHandler(),
        FileLoadHandler(),
        WebSearchHandler(),
        ScrapeWebPage(),
    ]
    
    for h in handlers:
        handler.add_handler(h)
    return handler
