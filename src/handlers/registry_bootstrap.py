from src.handlers.handler_registry import HandlerRegistry
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2 
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.scrape_web_page_handler2 import ScrapeWebPageHandler2
from src.handlers.web_search_handler2 import WebSearchHandler2


def build_registry() -> HandlerRegistry:
    reg = HandlerRegistry()
    reg.register(FileLoadHandler2)
    reg.register(FileSaveHandler2)
    reg.register(CommandExecutionHandler2)
    reg.register(ScrapeWebPageHandler2)
    reg.register(WebSearchHandler2)
    return reg
