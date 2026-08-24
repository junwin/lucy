from __future__ import annotations
import os
import sys

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import Mock

import pytest


# Ensure repo root is on sys.path so `import src...` works in tests.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)



# NOTE: tests use FakeStorage fixture below for most unit tests.
# Some tests construct JsonFileStorage directly rather than using a fixture.

# -----------------------------------------------------------------------------
# Fakes (test infrastructure)
# -----------------------------------------------------------------------------

@dataclass
class FakeConfig:
    values: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


@dataclass
class FakeStorage:
    """In-memory storage implementing the subset of the storage interface used by tests."""

    # contexts keyed by (account_name, context_id)
    contexts: Dict[tuple[str, str], Any] = field(default_factory=dict)

    # -------------------------
    # Contexts
    # -------------------------

    def save_context(self, context: Any) -> None:
        self.contexts[(context.account_name, context.id)] = context

    def get_context(self, account_name: str, context_id: str) -> Optional[Any]:
        return self.contexts.get((account_name, context_id))

    def list_context_names(self, account_name: str) -> List[str]:
        """Return sorted context ids for the given account."""
        names = [
            ctx_id
            for (acct, ctx_id) in self.contexts.keys()
            if acct == account_name
        ]
        return sorted(set(names))


class FakeHandler:
    def __init__(self, result: Any = None, exc: Optional[BaseException] = None):
        self._result = result
        self._exc = exc
        self.calls: List[Any] = []

    def execute(self, args: Dict[str, Any], account_name: Optional[str] = None, **context) -> Any:
        self.calls.append((args, account_name, context))
        if self._exc is not None:
            raise self._exc
        return self._result


class FakeRegistry:
    def __init__(self, handler_by_name: Optional[Dict[str, Any]] = None, tool_defs: Optional[List[dict]] = None):
        self._handler_by_name = handler_by_name or {}
        self._tool_defs = tool_defs if tool_defs is not None else []

    def tools(self) -> List[dict]:
        return self._tool_defs

    def has_tool(self, name: str) -> bool:
        return name in self._handler_by_name

    def tool_names(self) -> List[str]:
        return sorted(self._handler_by_name.keys())

    def create(self, name: str, config: Any = None) -> Any:
        return self._handler_by_name[name]


@dataclass
class FakeAgent:
    name: str = "lucy"
    model: str = "test-model"
    temperature: float = 0.0
    context_type: str = "hybrid"
    max_function_call_iterations: int = 5
    save_responses: bool = False
    delegation_depth: int = 0
    max_delegation_depth: int = 1
    default_context: Optional[str] = None


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def setup_no_tool_calls(llm_adapter: Mock, *, response_id: str = "r1", text: str = "hello!") -> None:
    resp = object()
    llm_adapter.call_model.return_value = resp
    llm_adapter.get_response_id.return_value = response_id
    llm_adapter.extract_tool_calls.return_value = []
    llm_adapter.get_text.return_value = text


def setup_tool_then_text(
    llm_adapter: Mock,
    *,
    tool_name: str,
    call_id: str = "call-1",
    tool_args: str = "{}",
    first_response_id: str = "r1",
    second_response_id: str = "r2",
    final_text: str = "final",
) -> None:
    resp1, resp2 = object(), object()
    llm_adapter.call_model.side_effect = [resp1, resp2]
    llm_adapter.get_response_id.side_effect = [first_response_id, second_response_id]
    llm_adapter.extract_tool_calls.side_effect = [
        [{"name": tool_name, "id": call_id, "arguments": tool_args}],
        [],
    ]
    llm_adapter.format_tool_output.side_effect = lambda call_id, output, **kwargs: {
        "type": "function_call_output",
        "call_id": call_id,
        "output": output,
    }
    llm_adapter.get_text.return_value = final_text


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def config() -> FakeConfig:
    return FakeConfig()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def prompt_builder(storage) -> Mock:
    pb = Mock()
    pb.build_prompt.return_value = [{"role": "user", "content": "hi"}]
    pb.storage = storage
    return pb


@pytest.fixture
def llm_adapter() -> Mock:
    llm = Mock()
    # default: no tools, simple text
    setup_no_tool_calls(llm, text="ok")
    return llm


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture
def make_proc(config, registry, storage, prompt_builder, llm_adapter) -> Callable[..., Any]:
    """
    Factory fixture to build FunctionCallingProcessor with optional overrides.
    """
    from src.message_processors.function_calling_processor import FunctionCallingProcessor

    def _make(**overrides):
        return FunctionCallingProcessor(
            config=overrides.get("config", config),
            registry=overrides.get("registry", registry),
            prompt_builder=overrides.get("prompt_builder", prompt_builder),
            llm_adapter=overrides.get("llm_adapter", llm_adapter),
        )

    return _make
