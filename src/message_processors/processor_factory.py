# src/message_processors/processor_factory.py

from injector import inject, Injector

from src.message_processors.function_calling_processor import FunctionCallingProcessor
from src.message_processors.automation_processor import AutomationProcessor


class ProcessorFactory:
    """
    Maps agent-config "message_processor" strings to concrete processor instances.
    Uses Injector to construct processors so dependencies are injected.
    """

    @inject
    def __init__(self, injector: Injector):
        self.injector = injector

        self._registry = {
            "function_calling_processor": FunctionCallingProcessor,
            "automation_processor": AutomationProcessor,
        }

    def get(self, processor_name: str):
        key = (processor_name or "").strip().lower()
        cls = self._registry.get(key)
        if not cls:
            raise ValueError(f"Unknown message_processor '{processor_name}'")
        return self.injector.get(cls)
