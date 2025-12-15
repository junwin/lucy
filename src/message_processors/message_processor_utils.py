import logging
import json
from typing import Any, Dict
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



def setup_action_dict(response_message: Dict[str, Any]) -> Dict[str, Any]:
    fc = response_message.get("function_call") or {}
    function_name = fc.get("name") or ""
    raw_args = fc.get("arguments")

    function_args: Dict[str, Any] = {}

    # 1) If args are already a dict, just use them
    if isinstance(raw_args, dict):
        function_args = raw_args

    # 2) If args are None/empty, keep {}
    elif raw_args is None:
        function_args = {}

    # 3) If args are a string, try to parse robustly
    elif isinstance(raw_args, str):
        args_text = raw_args.strip()

        # Strip common code fences
        if args_text.startswith("```"):
            args_text = args_text.strip("`")
            # If it started with ```json, remove the leading "json"
            args_text = args_text.lstrip().removeprefix("json").strip()

        if args_text == "":
            function_args = {}
        else:
            try:
                function_args = json.loads(args_text)
            except json.JSONDecodeError as e:
                # Try a minimal salvage: replace single quotes with double quotes
                # (only safe-ish for simple cases)
                try_text = args_text.replace("'", '"')
                try:
                    function_args = json.loads(try_text)
                    logging.warning(
                        "Parsed tool args after single-quote normalization for %s",
                        function_name,
                    )
                except json.JSONDecodeError:
                    preview = (args_text[:200] + "…") if len(args_text) > 200 else args_text
                    logging.error(
                        "Failed to parse tool args for %s: %s; args preview=%r",
                        function_name,
                        str(e),
                        preview,
                    )
                    function_args = {}
    else:
        # unexpected type
        logging.warning(
            "Unexpected type for tool args for %s: %s",
            function_name,
            type(raw_args).__name__,
        )
        function_args = {}

    action_dict: Dict[str, Any] = {"action_name": function_name}

    if isinstance(function_args, dict):
        action_dict.update(function_args)
    else:
        # If the model returns a list/primitive (rare), keep it under a standard key
        action_dict["arguments"] = function_args

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
