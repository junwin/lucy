from datetime import datetime, timezone
from types import SimpleNamespace

from src.coala_memory.procedural import (
    ContextProceduralMemory,
    ProceduralMemory,
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
    ProceduralSkill,
)
from src.coala_memory.semantic import (
    SemanticDocument,
    SemanticMemory,
    SemanticMemoryRequest,
    SemanticMemoryResult,
)
from src.prompt_builders.coala_prompt_builder import CoALAPromptBuilder
from src.storage.models import Context, Skill


class _Config:
    def get(self, key, default=None):
        return default


class _AgentManager:
    def __init__(self, agent):
        self.agent = agent

    def get_agent(self, name):
        return self.agent


class _Storage:
    def get_or_create_context(self, account_name, context_name):
        raise AssertionError("PromptBuilder should use ProceduralMemory, not storage context lookup")


class _ContextStore:
    def __init__(self, context):
        self.context = context
        self.get_or_create_calls = 0
        self.get_calls = 0

    def get_or_create_context(self, account_name, context_id):
        self.get_or_create_calls += 1
        return self.context

    def get_context(self, account_name, context_id):
        self.get_calls += 1
        return self.context


class _FakeProceduralMemory(ProceduralMemory):
    def __init__(self):
        self.requests = []

    def recall(self, request: ProceduralMemoryRequest) -> ProceduralMemoryResult:
        self.requests.append(request)
        return ProceduralMemoryResult(
            context_id="lucyproject",
            account_name="junwin",
            tag="lucy",
            text="Project body",
            resolved_text="Project body\n\n## skill: github\nUse GitHub carefully.",
            imports=["github"],
            skills=[
                ProceduralSkill(
                    name="github",
                    text="Use GitHub carefully.",
                    mandatory_tools=["github_issue"],
                )
            ],
            required_tools=["github_issue"],
            search_namespaces=["documents"],
            metadata={"extra": {"owner": "junwin"}},
        )


class _FakeSemanticMemory(SemanticMemory):
    def __init__(self):
        self.requests = []

    def recall(self, request: SemanticMemoryRequest) -> SemanticMemoryResult:
        self.requests.append(request)
        return SemanticMemoryResult(
            documents=[
                SemanticDocument(
                    source_id="doc-1",
                    title="Prompt builders",
                    snippet="Semantic document text",
                    score=0.8,
                )
            ],
            metadata={"backend": "fake"},
        )


def _agent():
    return SimpleNamespace(
        system_prompt="You are Peace.",
        persona="",
        style_prompt="",
        use_embeddings=True,
        default_context="lucyproject",
        context_type="hybrid",
        max_prompt_documents=3,
        max_prompt_conversations=0,
        allowed_tools=[],
        prompt_budget_max_tokens=None,
        context_text_soft_max_tokens=None,
    )


def test_context_procedural_memory_maps_resolved_context_and_skills():
    context = Context(
        id="lucyproject",
        account_name="junwin",
        updated_at=datetime.now(timezone.utc),
        text="Project body",
        tag="lucy",
        imports=["github"],
        mandatory_tools=["context_tool"],
        search_namespaces=["documents"],
        extra={"owner": "junwin"},
        resolved_skills=[
            Skill(
                name="github",
                text="Use GitHub carefully.",
                mandatory_tools=["github_issue"],
                extra={"kind": "workflow"},
            )
        ],
        missing_imports=["missing_skill"],
    )
    store = _ContextStore(context)
    memory = ContextProceduralMemory(store)

    result = memory.recall(
        ProceduralMemoryRequest(
            account_name="junwin",
            context_name="lucyproject",
        )
    )

    assert store.get_or_create_calls == 1
    assert result.context_id == "lucyproject"
    assert result.tag == "lucy"
    assert result.resolved_text == "Project body\n\n## skill: github\nUse GitHub carefully."
    assert result.search_namespaces == ["documents"]
    assert result.required_tools == ["context_tool", "github_issue"]
    assert result.missing_imports == ["missing_skill"]
    assert result.skills[0].name == "github"
    assert result.skills[0].metadata == {"kind": "workflow"}
    assert result.metadata["extra"] == {"owner": "junwin"}


def test_context_procedural_memory_can_read_without_creating():
    context = Context(
        id="existing",
        account_name="junwin",
        updated_at=datetime.now(timezone.utc),
    )
    store = _ContextStore(context)
    memory = ContextProceduralMemory(store)

    result = memory.recall(
        ProceduralMemoryRequest(
            account_name="junwin",
            context_name="existing",
            create_if_missing=False,
        )
    )

    assert result.context_id == "existing"
    assert store.get_calls == 1
    assert store.get_or_create_calls == 0


def test_prompt_builder_recalls_procedural_context_once_and_routes_namespaces():
    procedural = _FakeProceduralMemory()
    semantic = _FakeSemanticMemory()
    builder = CoALAPromptBuilder(
        agent_manager=_AgentManager(_agent()),
        config=_Config(),
        storage=_Storage(),
        semantic_memory=semantic,
        procedural_memory=procedural,
    )

    messages = builder.build_prompt(
        content_text="tell me about prompt builders",
        conversation_id="none",
        agent_name="peace",
        account_name="junwin",
        context_type="hybrid",
    )

    assert len(procedural.requests) == 1
    request = procedural.requests[0]
    assert request.account_name == "junwin"
    assert request.context_name == "lucyproject"
    assert request.include_resolved_text is True
    assert request.include_skills is True
    assert request.include_required_tools is True

    assert len(semantic.requests) == 1
    assert semantic.requests[0].namespaces == ["documents"]

    text_messages = [m["content"] for m in messages if isinstance(m.get("content"), str)]
    assert any(
        "id: lucyproject\naccount_name: junwin\ntag: lucy" in text
        and "## skill: github\nUse GitHub carefully." in text
        for text in text_messages
    )
    assert any("Semantic document text" in text for text in text_messages)


def test_prompt_builder_procedural_cache_is_scoped_to_one_build():
    procedural = _FakeProceduralMemory()
    builder = CoALAPromptBuilder(
        agent_manager=_AgentManager(_agent()),
        config=_Config(),
        storage=_Storage(),
        procedural_memory=procedural,
    )

    for question in ("one", "two"):
        builder.build_prompt(
            content_text=question,
            conversation_id="none",
            agent_name="peace",
            account_name="junwin",
            context_type="none",
        )

    assert len(procedural.requests) == 2
