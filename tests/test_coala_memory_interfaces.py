from src.coala_memory import (
    EpisodicMemoryRequest,
    EpisodicMemoryResult,
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
    SemanticMemoryRequest,
    SemanticMemoryResult,
)
from src.coala_memory.episodic import EpisodicDigest, EpisodicEvent
from src.coala_memory.procedural import ProceduralSkill
from src.coala_memory.semantic import SemanticDocument


def test_episodic_request_matches_prompt_history_and_digest_inputs():
    request = EpisodicMemoryRequest(
        account_name="junwin",
        agent_name="peace",
        conversation_id="session-1",
        query="what did we decide?",
        max_events=6,
        token_budget=1200,
        digest_top_k=3,
    )
    result = EpisodicMemoryResult(
        session_id=request.conversation_id,
        events=[EpisodicEvent(role="user", content="hello")],
        digests=[EpisodicDigest(session_id="old-session", snippet="decision", score=0.4)],
    )

    assert request.max_events == 6
    assert result.events[0].role == "user"
    assert result.digests[0].score == 0.4


def test_semantic_request_supports_embedding_and_document_modes():
    request = SemanticMemoryRequest(
        account_name="junwin",
        query="CoALA memory",
        use_embeddings=True,
        namespaces=["external"],
        docs_tag="lucy",
        top_k=3,
    )
    result = SemanticMemoryResult(
        documents=[SemanticDocument(source_id="note-1", title="Memory", snippet="text", score=0.7)]
    )

    assert request.use_embeddings is True
    assert request.docs_tag == "lucy"
    assert result.documents[0].source_id == "note-1"


def test_procedural_request_exposes_resolved_context_skill_and_tool_state():
    request = ProceduralMemoryRequest(account_name="junwin", context_name="lucyproject")
    result = ProceduralMemoryResult(
        context_id="lucyproject",
        account_name="junwin",
        resolved_text="Project context\n\n## skill: github\nUse GitHub",
        skills=[ProceduralSkill(name="github", text="Use GitHub", mandatory_tools=["github_issue"])],
        required_tools=["github_issue"],
        search_namespaces=["external"],
    )

    assert request.create_if_missing is True
    assert result.skills[0].name == "github"
    assert result.required_tools == ["github_issue"]
