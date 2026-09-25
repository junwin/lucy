from types import SimpleNamespace

from galet_prompt_builder import CompiledPrompt, PromptMessage, PromptMetrics
from galet_prompt_builder.metrics import SectionMetrics

from galet_memory import (
    EpisodicEvent,
    EpisodicMemoryResult,
)
from src.coala_memory.procedural import ProceduralMemoryResult
from src.coala_memory.semantic import (
    SemanticDocument,
    SemanticMemoryResult,
)

from src.prompt_builders.galet_prompt_builder_adapter import (
    GaletPromptBuilderAdapter,
    GaletPromptPolicy,
)


class _Config:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


class _AgentManager:
    def __init__(self, agent):
        self.agent = agent

    def get_agent(self, name):
        assert name == self.agent.name
        return self.agent


class _ProceduralMemory:
    def __init__(self):
        self.requests = []

    def recall(self, request):
        self.requests.append(request)
        return SimpleNamespace(search_namespaces=["vol_6", "documents"])


class _UnusedMemory:
    def recall(self, request):  # pragma: no cover - compiler is replaced
        raise AssertionError("recording compiler must not retrieve memory")


class _RecordingCompiler:
    instance = None

    def __init__(self, **memories):
        self.memories = memories
        self.compile_args = None
        type(self).instance = self

    def compile(self, request, budgets, limits):
        self.compile_args = (request, budgets, limits)
        empty = SectionMetrics(budget_tokens=0)
        metrics = PromptMetrics(
            total_limit_tokens=budgets.total_tokens,
            total_used_tokens=25,
            safety_margin_tokens=budgets.safety_margin_tokens,
            system=SectionMetrics(budget_tokens=10, used_tokens=10),
            procedural=empty,
            episodic_events=SectionMetrics(
                budget_tokens=budgets.episodic_event_tokens,
                used_tokens=5,
            ),
            episodic_digests=empty,
            semantic=SectionMetrics(
                budget_tokens=budgets.semantic_tokens,
                used_tokens=7,
            ),
            current_input=SectionMetrics(budget_tokens=3, used_tokens=3),
        )
        return CompiledPrompt(
            messages=(
                PromptMessage("system", "Lucy system", "system"),
                PromptMessage("user", request.current_input, "current_input"),
            ),
            metrics=metrics,
        )


def _agent(**overrides):
    values = dict(
        name="peace",
        system_prompt="You are Peace.",
        persona="Careful developer.",
        style_prompt="Be concise.",
        default_context="lucyproject",
        use_embeddings=True,
        max_prompt_conversations=4,
        max_prompt_documents=2,
        prompt_budget_max_tokens=5000,
        allowed_tools=[],
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_adapter_translates_lucy_call_to_explicit_galet_policy():
    procedural = _ProceduralMemory()
    adapter = GaletPromptBuilderAdapter(
        agent_manager=_AgentManager(_agent()),
        config=_Config(
            {
                "galet_prompt_builder": {
                    "episodic_event_tokens": 700,
                    "semantic_score_threshold": 0.25,
                }
            }
        ),
        storage=SimpleNamespace(),
        semantic_memory=_UnusedMemory(),
        episodic_memory=_UnusedMemory(),
        procedural_memory=procedural,
        compiler_class=_RecordingCompiler,
    )

    messages = adapter.build_prompt(
        content_text="What did I write about attention?",
        conversation_id="session-1",
        agent_name="peace",
        account_name="junwin",
        context_type="hybrid",
        extra_system_messages=["Environment block"],
    )

    request, budgets, limits = _RecordingCompiler.instance.compile_args
    assert (
        _RecordingCompiler.instance.memories["episodic_memory"]
        is adapter.episodic_memory
    )
    assert request.current_input == "What did I write about attention?"
    assert request.context_name == "lucyproject"
    assert request.semantic_namespaces == ("vol_6", "documents")
    assert request.semantic_score_threshold == 0.25
    assert request.episodic_event_kinds == (
        "user_message",
        "assistant_message",
        "session_digest",
    )
    assert request.include_structured_episodic_events is False
    assert request.system_instructions == (
        "You are Peace.\n\nCareful developer.\n\nBe concise.",
        "Current session ID: session-1",
        "Environment block",
    )
    assert budgets.total_tokens == 5000
    assert budgets.episodic_event_tokens == 700
    assert budgets.semantic_tokens == 1000
    assert limits.maximum_events == 4
    assert limits.maximum_semantic_documents == 2
    assert messages[-1] == {
        "role": "user",
        "content": "What did I write about attention?",
    }
    assert adapter._last_prompt_token_breakdown == {
        "system_session": 10,
        "context_text": 0,
        "obsidian_notes": 7,
        "digest_embeddings": 0,
        "chat_history": 5,
        "current_user_message": 3,
        "total_without_handlers": 25,
    }


def test_adapter_disables_semantic_budget_when_agent_disables_embeddings():
    adapter = GaletPromptBuilderAdapter(
        agent_manager=_AgentManager(_agent(use_embeddings=False)),
        config=_Config(),
        storage=SimpleNamespace(),
        semantic_memory=_UnusedMemory(),
        episodic_memory=_UnusedMemory(),
        procedural_memory=_ProceduralMemory(),
        compiler_class=_RecordingCompiler,
    )

    adapter.build_prompt(
        content_text="Question",
        conversation_id="new",
        agent_name="peace",
        account_name="junwin",
        context_type="hybrid",
    )

    request, budgets, _ = _RecordingCompiler.instance.compile_args
    assert request.include_semantic is False
    assert budgets.semantic_tokens == 0


def test_policy_defaults_are_explicit_and_agent_limits_win():
    policy = GaletPromptPolicy.from_config(_Config(), _agent())

    assert policy.total_tokens == 5000
    assert policy.maximum_events == 4
    assert policy.maximum_semantic_documents == 2
    assert policy.episodic_event_tokens == 1000
    assert policy.semantic_score_threshold == 0.30


def test_adapter_compiles_with_lucy_memory_contracts():
    class Semantic:
        def recall(self, request):
            return SemanticMemoryResult(
                documents=[
                    SemanticDocument(
                        source_id="attention.md",
                        title="Attention",
                        snippet="Attention is shaped by perception.",
                        score=0.9,
                    )
                ]
            )

    class Episodic:
        def recall(self, request):
            return EpisodicMemoryResult(
                session_id="session-1",
                events=[
                    EpisodicEvent(
                        role="user",
                        content="Earlier question",
                        kind="user_message",
                        event_id="event-1",
                    )
                ],
            )

        def save_overflow_digest(self, **kwargs):
            return None

    class Procedural:
        def recall(self, request):
            return ProceduralMemoryResult(
                context_id="lucyproject",
                account_name="junwin",
                resolved_text="Use the project conventions.",
                search_namespaces=["documents"],
            )

    adapter = GaletPromptBuilderAdapter(
        agent_manager=_AgentManager(_agent(prompt_budget_max_tokens=4000)),
        config=_Config(),
        storage=SimpleNamespace(),
        semantic_memory=Semantic(),
        episodic_memory=Episodic(),
        procedural_memory=Procedural(),
    )

    messages = adapter.build_prompt(
        content_text="What did I write about attention?",
        conversation_id="session-1",
        agent_name="peace",
        account_name="junwin",
        context_type="hybrid",
        context_name="lucyproject",
    )

    contents = [message["content"] for message in messages]
    assert any("Use the project conventions" in value for value in contents)
    assert any("Earlier question" in value for value in contents)
    assert any("Attention is shaped by perception" in value for value in contents)
    assert messages[-1]["content"] == "What did I write about attention?"
