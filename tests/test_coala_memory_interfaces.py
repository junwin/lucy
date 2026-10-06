from src.coala_memory.procedural import (
    ProceduralMemoryRequest,
    ProceduralMemoryResult,
    ProceduralSkill,
)
from src.coala_memory.semantic import (
    SemanticDocument,
    SemanticMemoryRequest,
    SemanticMemoryResult,
)


def test_semantic_request_supports_embedding_recall():
    request = SemanticMemoryRequest(
        account_name="junwin",
        query="CoALA memory",
        use_embeddings=True,
        namespaces=["documents"],
        top_k=3,
        embedding_model="text-embedding-3-small",
        source_type="obsidian_note",
    )
    result = SemanticMemoryResult(
        documents=[
            SemanticDocument(
                source_id="note-1",
                title="Memory",
                snippet="text",
                score=0.7,
                source_type="obsidian_note",
            )
        ]
    )

    assert request.use_embeddings is True
    assert request.namespaces == ["documents"]
    assert request.embedding_model == "text-embedding-3-small"
    assert request.source_type == "obsidian_note"
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
