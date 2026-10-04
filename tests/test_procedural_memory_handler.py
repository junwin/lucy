import json
from types import SimpleNamespace
from unittest.mock import Mock

from galet_tools.tools.procedural_memory_handler import (
    ProceduralMemoryHandler as GaletProceduralMemoryHandler,
)

from src.handlers.procedural_memory_handler import ProceduralMemoryHandler
from src.handlers.registry_bootstrap import build_registry_and_catalog
from src.message_processors.fcp_models import _ToolCall
from src.message_processors.fcp_tool_executor import ToolExecutor
from src.procedural_memory_config import build_procedural_memory


def _config(tmp_path, **overrides):
    return {
        "storage_root_path": str(tmp_path),
        "storage_namespace": "data",
        **overrides,
    }


def test_registered_adapter_uses_lucy_paths_and_existing_permissions(tmp_path):
    registry, catalog = build_registry_and_catalog()
    assert "lucy:procedural_memory" in {item.id for item in catalog.descriptors()}
    handler = registry.create("procedural_memory", config=_config(tmp_path))
    assert isinstance(handler, GaletProceduralMemoryHandler)

    for action, name_key, name, text in (
        ("save_skill", "skill_name", "review", "Review carefully"),
        ("save_context", "context_name", "dev", "Development context"),
    ):
        result = handler.execute(
            {"action": action, name_key: name, "scope": "account", "text": text,
             "frontmatter": {"imports": ["review"]} if action == "save_context" else {}},
            account_name="junwin",
        )
        assert result["ok"], result

    assert (tmp_path / "data/contexts/junwin/dev.md").exists()
    assert (tmp_path / "data/skills/junwin/review.md").exists()
    recalled = handler.execute({"action": "recall", "context_name": "dev"}, account_name="junwin")
    assert recalled["memory"]["text"] == "Development context"
    assert recalled["memory"]["skills"][0]["text"] == "Review carefully"
    rejected = handler.execute(
        {"action": "list_contexts", "account_name": "another-account"}, account_name="junwin",
    )
    assert rejected["ok"] is False
    assert registry.eligible_tool_defs(SimpleNamespace(name="test", allowed_tools=[]), None) == []
    allowed = registry.eligible_tool_defs(
        SimpleNamespace(name="test", allowed_tools=["procedural_memory"]), None,
    )
    assert [item["name"] for item in allowed] == ["procedural_memory"]


def test_adapter_honors_configured_procedural_root_and_injected_backend(tmp_path):
    config = _config(tmp_path, procedural_memory={"root": str(tmp_path / "custom")})
    handler = ProceduralMemoryHandler(config)
    result = handler.execute(
        {"action": "save_context", "scope": "global", "context_name": "dev", "text": "Custom"},
        account_name="junwin",
    )
    assert result["ok"], result
    assert (tmp_path / "custom/contexts/dev.md").exists()
    injected = build_procedural_memory(_config(tmp_path / "injected"))
    assert ProceduralMemoryHandler(config, memory=injected).memory is injected


def test_tool_executor_uses_prompt_builders_procedural_backend(tmp_path):
    config = _config(tmp_path)
    # A different root proves the executor passes the actual shared backend,
    # rather than using the adapter's separately constructed fallback.
    shared = build_procedural_memory(_config(tmp_path / "shared"))
    shared.repository.save_context(
        account_name="junwin", context_name="dev", scope="account", text="Shared context",
    )
    registry, _ = build_registry_and_catalog()
    executor = ToolExecutor(
        registry=registry, config=config,
        prompt_builder=SimpleNamespace(procedural_memory=shared),
        llm_adapter=Mock(), agent_manager=None,
    )
    _, results = executor.execute_tool_calls(
        tool_calls=[_ToolCall(name="procedural_memory", call_id="call-1",
                             arguments_raw=json.dumps({"action": "recall", "context_name": "dev"}))],
        primary_agent=SimpleNamespace(name="test", allowed_tools=["procedural_memory"]),
        secondary_agent=None, processor_factory=None, account={"accountId": "junwin"},
        ctx=SimpleNamespace(account_id="junwin", conversation_id="session", context_name="none",
                            agent_name="test", provider="openai"),
        metrics={"tool_calls": 0},
    )
    recalled = json.loads(results[0][1])
    assert recalled["ok"], recalled
    assert recalled["memory"]["text"] == "Shared context"
