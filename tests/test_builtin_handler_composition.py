"""Lucy #258: package built-ins compose without host-specific registrations."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from galet_tools import HandlerRegistry, HandlerV2
from galet_tools import composition
from galet_tools.composition import BuiltinHandler
from galet_tools.tools.execute_command2 import ExecuteCommand2

from src.handlers import registry_bootstrap
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.message_processors.fcp_models import _ToolCall
from src.message_processors.fcp_tool_executor import ToolExecutor


class FuturePackageHandler(HandlerV2):
    """Simulate a new release adding a tool Lucy has never imported."""
    def __init__(self, storage_resolver):
        self.storage_resolver = storage_resolver

    @classmethod
    def name(cls):
        return "future_package_tool"

    @classmethod
    def tool_def(cls):
        return {"type": "function", "name": cls.name(), "description": "Future package tool",
                "parameters": {"type": "object", "properties": {}}}

    def execute(self, args, *, account_name="auto", **context):
        result = {"ok": True, "root": self.storage_resolver.external_root_dir("repo"),
                  "account_name": account_name}
        for key in ("semantic_memory", "episodic_store", "procedural_memory"):
            context[key].check(account_name)
            result[key] = True
        return result


@pytest.fixture
def future_package(monkeypatch):
    original = composition.builtin_handlers
    spec = BuiltinHandler(__name__ + ":FuturePackageHandler", ("storage_resolver",),
                          (("storage_resolver", "storage_resolver"),))
    monkeypatch.setattr(composition, "builtin_handlers", lambda: (*original(), spec))


def test_new_package_handler_enters_registry_catalog_and_permissions(future_package):
    registry, catalog = registry_bootstrap.build_registry_and_catalog()
    assert registry.has_tool("future_package_tool")
    assert catalog.get("future_package_tool").id == "galet-tools:future_package_tool"
    assert catalog.get("file_load").id == "lucy:file_load"
    assert catalog.create("lucy:file_load", config={}).__class__ is FileLoadHandler2
    assert registry.eligible_tool_names(SimpleNamespace(name="test", allowed_tools=[])) == []
    agent = SimpleNamespace(name="test", allowed_tools=["future_package_tool"])
    assert registry.eligible_tool_names(agent) == ["future_package_tool"]
    context = SimpleNamespace(extra={"allowed_tools": ["file_load"]})
    assert registry.eligible_tool_names(agent, context) == []


def test_collision_preserves_lucy_adapter_and_backend_factory(monkeypatch):
    backend_handler = object()

    class HostRegistry(HandlerRegistry):
        def register(self, cls, *, factory=None):
            if cls is FileLoadHandler2:
                factory = lambda config: backend_handler
            super().register(cls, factory=factory)

    monkeypatch.setattr(registry_bootstrap, "HandlerRegistry", HostRegistry)
    registry, catalog = registry_bootstrap.build_registry_and_catalog()
    assert catalog.create("lucy:file_load", config={}) is backend_handler
    # Lucy's structured execute_command public API wins over the package's
    # legacy execute_command, while the distinct execute_command2 is discovered.
    assert type(registry.create("execute_command", config={})) is CommandExecutionHandler2
    assert type(registry.create("execute_command2", config={})) is ExecuteCommand2
    assert catalog.get("execute_command").source == "lucy"
    assert catalog.get("execute_command2").source == "galet-tools"
    assert catalog.get("episodic_list_sessions").source == "galet-tools"


def test_new_generic_tool_executes_with_lucy_ports_and_shared_memory(future_package, tmp_path):
    registry, _ = registry_bootstrap.build_registry_and_catalog()
    config = {"storage_root_path": str(tmp_path), "storage_namespace": "data",
              "external_roots": {"repo": str(tmp_path)}}
    semantic, episodic, procedural = Mock(), Mock(), Mock()
    executor = ToolExecutor(
        registry=registry, config=config, episodic_store=episodic,
        prompt_builder=SimpleNamespace(semantic_memory=semantic, procedural_memory=procedural),
        llm_adapter=Mock(), agent_manager=None,
    )
    _, results = executor.execute_tool_calls(
        tool_calls=[_ToolCall(name="future_package_tool", call_id="call-1", arguments_raw="{}")],
        primary_agent=SimpleNamespace(name="test", allowed_tools=["future_package_tool"]),
        secondary_agent=None, processor_factory=None, account={"accountId": "john"},
        ctx=SimpleNamespace(account_id="john", conversation_id="session", context_name="none",
                            agent_name="test", provider="openai"),
        metrics={"tool_calls": 0},
    )
    result = json.loads(results[0][1])
    assert result == {"ok": True, "root": str(tmp_path), "account_name": "john",
                      "semantic_memory": True, "episodic_store": True, "procedural_memory": True}
    for memory in (semantic, episodic, procedural):
        memory.check.assert_called_once_with("john")


def test_discovery_and_constructor_ports_do_not_open_memory(monkeypatch, tmp_path):
    monkeypatch.setattr("src.memory_config.get_shared_memory", Mock(side_effect=AssertionError("unexpected memory startup")))
    registry, _ = registry_bootstrap.build_registry_and_catalog()
    config = {"storage_root_path": str(tmp_path), "storage_namespace": "data",
              "code_sandbox_path": str(tmp_path), "external_roots": {}}
    generic = registry.create("execute_command2", config=config)
    assert generic.execute({"mode": "process", "executable": "echo", "arguments": ["hello"],
                            "location": "external", "external_root": "missing"})["ok"] is False
    result = registry.create("episodic_list_sessions", config=config).execute({}, account_name="john")
    assert result["ok"] is False
    assert "not available" in result["error"]


def test_broken_builtin_registration_is_not_silently_ignored(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("invalid built-in registrar")
    monkeypatch.setattr(registry_bootstrap, "register_builtin_handlers", fail)
    with pytest.raises(RuntimeError, match="invalid built-in registrar"):
        registry_bootstrap.build_registry_and_catalog()


def test_package_episodic_operation_uses_executors_existing_store(tmp_path):
    from galet_memory import SqliteEpisodicMemory

    registry, _ = registry_bootstrap.build_registry_and_catalog()
    with SqliteEpisodicMemory(tmp_path / "episodic.sqlite") as memory:
        memory.create_session(account_name="john", session_id="visible")
        memory.create_session(account_name="other", session_id="private")
        executor = ToolExecutor(
            registry=registry, config={}, episodic_store=memory,
            prompt_builder=SimpleNamespace(), llm_adapter=Mock(), agent_manager=None,
        )
        _, results = executor.execute_tool_calls(
            tool_calls=[_ToolCall(name="episodic_list_sessions", call_id="call-1", arguments_raw="{}")],
            primary_agent=SimpleNamespace(name="test", allowed_tools=["episodic_list_sessions"]),
            secondary_agent=None, processor_factory=None, account={"accountId": "john"},
            ctx=SimpleNamespace(account_id="john", conversation_id="session", context_name="none",
                                agent_name="test", provider="openai"),
            metrics={"tool_calls": 0},
        )
        result = json.loads(results[0][1])
        assert result["ok"], result
        assert [session["session_id"] for session in result["sessions"]] == ["visible"]
