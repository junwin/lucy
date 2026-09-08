from types import SimpleNamespace
from unittest.mock import Mock

from src.coala_memory.procedural import ProceduralMemoryResult
from src.coala_memory.semantic import SemanticDocument, SemanticMemoryResult
from src.prompt_builders.coala_prompt_builder import CoALAPromptBuilder
from src.prompt_builders.prompt_builder import PromptBuilder


class RecordingSemanticMemory:
    def __init__(self) -> None:
        self.requests = []

    def recall(self, request):
        self.requests.append(request)
        return SemanticMemoryResult(
            documents=[
                SemanticDocument(
                    source_id="src_prompt_builders.md",
                    title="src_prompt_builders.md",
                    snippet="PromptBuilder semantic memory integration works.",
                    tags=["lucy"],
                    score=0.52,
                    truncated=False,
                    path="/tmp/src_prompt_builders.md",
                    source_type="documents",
                )
            ],
            metadata={"backend": "sqlite_vec"},
        )


class FakeProceduralMemory:
    def recall(self, request):
        return ProceduralMemoryResult(
            context_id=request.context_name,
            account_name=request.account_name,
            tag="lucyproject",
            resolved_text="",
            search_namespaces=["documents"],
        )


class FakeAgentManager:
    def __init__(self, agent) -> None:
        self.agent = agent

    def get_agent(self, name):
        return self.agent


class FakeConfig:
    def get(self, key, default=None):
        return default


def _agent():
    return SimpleNamespace(
        name="peace",
        system_prompt="You are peace.",
        persona="",
        style_prompt="",
        use_embeddings=True,
        max_prompt_documents=3,
        max_prompt_conversations=0,
        allowed_tools=[],
        context_text_soft_max_tokens=None,
        prompt_budget_max_tokens=None,
    )


def test_prompt_builder_uses_coala_semantic_memory_and_context_namespaces():
    memory = RecordingSemanticMemory()
    pb = CoALAPromptBuilder(
        agent_manager=FakeAgentManager(_agent()),
        config=FakeConfig(),
        storage=Mock(),
        semantic_memory=memory,
        procedural_memory=FakeProceduralMemory(),
    )
    pb._get_digest_context = Mock(return_value=[])

    messages = pb.build_prompt(
        content_text="i love the prompt_builder indeed i do",
        conversation_id="none",
        agent_name="peace",
        account_name="junwin",
        context_type="documents",
        context_name="lucy_design",
    )

    assert len(memory.requests) == 1
    request = memory.requests[0]
    assert request.account_name == "junwin"
    assert request.query == "i love the prompt_builder indeed i do"
    assert request.namespaces == ["documents"]
    assert request.top_k == 3
    assert request.max_chars == 9000
    assert request.score_threshold == 0.25
    assert request.use_embeddings is True

    prompt_text = "\n".join(str(message.get("content", "")) for message in messages)
    assert "src_prompt_builders.md" in prompt_text
    assert "PromptBuilder semantic memory integration works." in prompt_text
    assert "Tags: lucy" in prompt_text


def test_prompt_builder_semantic_helper_preserves_legacy_doc_context_shape():
    memory = RecordingSemanticMemory()
    pb = PromptBuilder(
        agent_manager=FakeAgentManager(_agent()),
        config=FakeConfig(),
        storage=Mock(),
        semantic_memory=memory,
    )

    contexts = pb._get_semantic_memory_context(
        query="prompt builder",
        account_name="junwin",
        namespaces=["documents"],
        top_k=5,
        max_chars=1200,
        score_threshold=0.30,
    )

    assert contexts == [
        {
            "title": "src_prompt_builders.md",
            "tags": ["lucy"],
            "snippet": "PromptBuilder semantic memory integration works.",
            "truncated": False,
            "score": 0.52,
            "source_id": "src_prompt_builders.md",
        }
    ]
    request = memory.requests[0]
    assert request.namespaces == ["documents"]
    assert request.top_k == 5
    assert request.max_chars == 1200
    assert request.score_threshold == 0.30
