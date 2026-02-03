# src/message_processors/processor_factory.py
from __future__ import annotations

"""ProcessorFactory

Important: keep imports lazy.

We previously imported processors at module import time, which can create
circular-import problems (e.g. AutomationProcessor -> ProcessorFactory ->
FunctionCallingProcessor -> ...).

Also important: processors must be constructed via Injector so required
dependencies are provided. Do not call processor constructors directly.
"""

from abc import ABC
from importlib import import_module

from injector import inject, Injector


class ProcessorFactory(ABC):
    """
    Maps agent-config "message_processor" strings to concrete processor instances.
    Uses Injector to construct processors so dependencies are injected.
    """

    @inject
    def __init__(self, injector: Injector):
        self.injector = injector

        # Map names to import paths. We resolve these lazily in get().
        self._registry: dict[str, str] = {
            "function_calling_processor": (
                "src.message_processors.function_calling_processor.FunctionCallingProcessor"
            ),
            "automation_processor": (
                "src.message_processors.automation_processor.AutomationProcessor"
            ),
            # New scaffold processor (Step 3.1). This is behind an unused
            # processor name so existing behaviour is unchanged.
            "task_running_processor": (
                "src.message_processors.task_running_processor.TaskRunningProcessor"
            ),
        }

    def get(self, processor_name: str):
        key = (processor_name or "").strip().lower()
        import_path = self._registry.get(key)
        if not import_path:
            raise ValueError(f"Unknown message_processor {processor_name}")

        module_name, class_name = import_path.rsplit(".", 1)
        module = import_module(module_name)
        cls = getattr(module, class_name)

        # Always construct via Injector so required dependencies are provided.
        return self.injector.get(cls)
