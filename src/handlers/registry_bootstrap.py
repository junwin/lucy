from src.handlers.handler_registry import HandlerRegistry
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2 


def build_registry() -> HandlerRegistry:
    reg = HandlerRegistry()
    reg.register(FileLoadHandler2)
    reg.register(FileSaveHandler2)
    return reg
