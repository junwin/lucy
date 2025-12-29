import logging
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2 
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.scrape_web_page_handler2 import ScrapeWebPageHandler2
from src.handlers.web_search_handler2 import WebSearchHandler2
from src.handlers.plan_tasks_handler import PlanTasksHandler  

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def build_registry() -> HandlerRegistry:
    logger.info("Building handler registry.")
    reg = HandlerRegistry()
    try:
        logger.debug("Registering FileLoadHandler2.")
        reg.register(FileLoadHandler2)
        logger.debug("Registering FileSaveHandler2.")
        reg.register(FileSaveHandler2)
        logger.debug("Registering CommandExecutionHandler2.")
        reg.register(CommandExecutionHandler2)
        logger.debug("Registering ScrapeWebPageHandler2.")
        reg.register(ScrapeWebPageHandler2)
        logger.debug("Registering WebSearchHandler2.")
        reg.register(WebSearchHandler2)
        logger.debug("Registering PlanTasksHandler.")
        reg.register(PlanTasksHandler)
    except Exception as e:
        logger.error("Error occurred while building the registry: %s", e)
        raise
    logger.info("Handler registry built successfully.")
    return reg
