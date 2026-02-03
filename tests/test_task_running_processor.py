from __future__ import annotations
from typing import Any

from src.message_processors.processor_factory import ProcessorFactory


class DummyInjector:
    def get(self, cls: type) -> Any:
        # naive construction for test: call with no args
        return cls()


def test_processor_factory_returns_task_running_processor():
    pf = ProcessorFactory(injector=DummyInjector())
    proc = pf.get("task_running_processor")
    assert proc is not None
    assert proc.__class__.__name__ == "TaskRunningProcessor"
    assert proc.process_message(primary_agent=None, account={}, message="hi") == "[TaskRunningProcessor] scaffold: no-op"
