"""Regression coverage for shared contexts through Lucy's runtime consumers."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from galet_memory import ProceduralMemoryRequest
from src.agent import Agent
from src.procedural_memory_config import build_procedural_memory
from src.prompt_builders.galet_prompt_builder_adapter import GaletPromptBuilderAdapter
from src.message_processors.fcp_tool_executor import load_context_state
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from src.tool_selection.pipeline import ToolSelectionPipeline
from tests.test_procedural_memory_config import Config
from tests.test_ask_request_handler import FakeProcessor, make_handler, make_payload


@pytest.fixture
def shared(tmp_path):
    config = Config(procedural_memory={"root": str(tmp_path / "custom"),
                    "layout": {"global_contexts": "shared/contexts"}})
    memory = build_procedural_memory(config)
    memory.repository.save_skill(account_name="alice", skill_name="writing", scope="global",
                                 text="Shared skill", frontmatter={"mandatory_tools": ["search"]})
    path = memory.repository.save_context(account_name="alice", context_name="shop", scope="global",
        text="Shared shop", frontmatter={"tag": "shared", "imports": ["writing"],
                                         "allowed_tools": ["search"]})
    return config, memory, path


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("account_override", [False, True])
def test_ask_does_not_shadow_existing_context(shared, streaming, account_override):
    _, memory, path = shared
    before = path.read_bytes()
    if account_override:
        memory.repository.save_context(account_name="alice", context_name="shop", text="Alice shop")
    class Processor(FakeProcessor):
        def process_message_streaming(self, **kwargs):
            self.calls.append(kwargs)
            yield "done"
    handler = make_handler(Processor(FCPResult(text="ok", metrics=RunMetrics())), Agent(name="lucy", default_context="shop"))
    handler.procedural_memory = memory
    request = make_payload(conversationId="existing")
    if streaming:
        assert list(handler.handle_streaming(request)) == ["done"]
    else:
        assert handler.handle(request)[0] == 200
    assert handler.storage.created == []
    assert path.read_bytes() == before
    assert (memory.repository.read_context("alice", "shop") is not None) == account_override
    assert memory.recall(ProceduralMemoryRequest("alice", "shop")).text == ("Alice shop" if account_override else "Shared shop")


def test_startup_creates_only_truly_missing_context(shared):
    _, memory, _ = shared
    handler = make_handler(FakeProcessor(FCPResult(text="ok", metrics=RunMetrics())), Agent(name="lucy"))
    handler.procedural_memory = memory
    handler._ensure_context("alice", "new-context")
    assert memory.repository.read_context("alice", "new-context") is not None
    handler._ensure_context("alice", "none")
    assert memory.repository.read_context("alice", "none") is None


@pytest.mark.parametrize("account_override", [False, True])
def test_tool_context_and_selection_resolve_shared_scopes(shared, account_override):
    config, memory, path = shared
    before = path.read_bytes()
    if account_override:
        memory.repository.save_context(account_name="alice", context_name="shop", text="Alice shop",
            frontmatter={"mandatory_tools": ["inspect"], "allowed_tools": ["inspect"]})
    builder = GaletPromptBuilderAdapter(agent_manager=Mock(), config=config, storage=Mock(),
        semantic_memory=Mock(), episodic_memory=Mock(), procedural_memory=memory)
    state = load_context_state(builder, "alice", "shop")
    expected = "inspect" if account_override else "search"
    assert state.text == ("Alice shop" if account_override else "Shared shop")
    assert state.required_tools == [expected]
    assert state.extra["allowed_tools"] == [expected]
    registry = SimpleNamespace(tools=lambda: [{"name": "search"}, {"name": "inspect"}])
    pipeline = ToolSelectionPipeline(registry, None, Mock(), {}, procedural_memory=memory)
    result = pipeline.resolve(Agent(name="lucy", allowed_tools=["search", "inspect"]), "alice", "shop", "hello")
    assert result.required == [expected]
    assert path.read_bytes() == before
    assert load_context_state(builder, "alice", "absent") is None
    assert memory.repository.read_context("alice", "absent") is None


@pytest.mark.parametrize("context,override,tag", [("shop", False, "shared"), ("shop", True, "account"), ("absent", False, None)])
def test_document_debug_uses_effective_tag_without_creating_files(shared, monkeypatch, context, override, tag):
    from src.http_endpoints import prompt_builder_debug_endpoints as endpoint
    config, memory, path = shared
    before = path.read_bytes()
    if override:
        memory.repository.save_context(account_name="alice", context_name="shop", text="Alice", frontmatter={"tag": "account"})
    monkeypatch.setattr(endpoint, "Keywords", lambda: SimpleNamespace(extract_keywords=lambda *a, **k: []))
    get_docs = Mock(return_value=[])
    monkeypatch.setattr(endpoint, "get_document_context", get_docs)
    storage = Mock()
    storage.list_documents.return_value = []
    body, status = endpoint.prompt_builder_debug_impl(storage, config,
        {"query": "hello", "accountName": "alice", "contextName": context})
    assert status == 200
    assert body["docs_tag_from_context"] == tag
    assert storage.list_documents.call_args.kwargs["tag"] == tag
    assert get_docs.call_args.kwargs["docs_tag"] == tag
    storage.get_or_create_context.assert_not_called()
    assert path.read_bytes() == before
    if not override:
        assert memory.repository.read_context("alice", context) is None


def test_legacy_read_fallbacks_never_create_contexts():
    from src.tool_selection.pipeline import get_required_tools
    storage = Mock()
    storage.get_context.return_value = SimpleNamespace(required_tools=["search"])
    builder = SimpleNamespace(storage=storage)
    assert load_context_state(builder, "alice", "shop") is storage.get_context.return_value
    assert get_required_tools(storage, "alice", "shop") == ["search"]
    storage.get_or_create_context.assert_not_called()
