# ==============================================================================
# FILE 4: tests/storage/test_storage_contexts.py
# ==============================================================================

import pytest
import os
from pathlib import Path
from datetime import datetime, timezone
from src.storage.models import ContextState
from src.storage_paths.storage_paths import StoragePaths


class TestContexts:
    """Test context/whiteboard operations."""

    def test_save_and_load_context(self, storage):
        """Test saving and loading context state."""
        context = ContextState(
            id="therapy_session_001",
            account_name="junwin",
            data={
                "goal": "retirement planning",
                "facts": ["retired 2023", "moved to Evanston"],
                "mood": "reflective",
            },
            updated_at=datetime.now(timezone.utc),
        )

        storage.save_context(context)

        retrieved = storage.get_context("junwin", "therapy_session_001")
        assert retrieved is not None
        assert retrieved.id == "therapy_session_001"
        assert retrieved.data["goal"] == "retirement planning"
        assert "retired 2023" in retrieved.data["facts"]

    def test_update_context(self, storage):
        """Test updating existing context."""
        context = ContextState(
            id="ctx_001",
            account_name="junwin",
            data={"count": 1},
            updated_at=datetime.now(timezone.utc),
        )
        storage.save_context(context)

        context.data["count"] = 2
        context.data["new_field"] = "value"
        context.updated_at = datetime.now(timezone.utc)
        storage.save_context(context)

        retrieved = storage.get_context("junwin", "ctx_001")
        assert retrieved.data["count"] == 2
        assert retrieved.data["new_field"] == "value"

    def test_get_nonexistent_context(self, storage):
        """Test retrieving a context that doesn't exist."""
        result = storage.get_context("junwin", "nonexistent")
        assert result is None

    def test_list_context_names_sorted(self, storage):
        """Lists context names (filename stems) for an account in sorted order."""
        # Create contexts out of lexical order.
        for ctx_id in ["b_ctx", "a_ctx", "c_ctx"]:
            storage.save_context(
                ContextState(
                    id=ctx_id,
                    account_name="junwin",
                    data={"id": ctx_id},
                    updated_at=datetime.now(timezone.utc),
                )
            )

        # New API (preferred)
        assert hasattr(storage, "list_context_names"), "storage must implement list_context_names"
        names = storage.list_context_names("junwin")
        assert names == ["a_ctx", "b_ctx", "c_ctx"]

    def test_list_context_names_missing_account_returns_empty(self, storage):
        """Missing account directory should return an empty list."""
        assert hasattr(storage, "list_context_names"), "storage must implement list_context_names"
        assert storage.list_context_names("account_does_not_exist") == []


class TestSkillLoading:
    """Test skill file loading via JsonFileStorage.get_skill_text."""

    @pytest.fixture
    def skill_storage(self, tmp_path: Path):
        """Create a real JsonFileStorage with a temp directory."""
        from src.storage.json_file_storage import JsonFileStorage

        storage_root = tmp_path / "lucy_storage"
        storage_root.mkdir()
        paths = StoragePaths(str(storage_root), "data")
        return JsonFileStorage(paths)

    def _write_skill(self, storage, account_name: str, skill_name: str, content: str):
        """Write a skill file to the test storage."""
        skill_dir = storage.storage_paths.skills / account_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / f"{skill_name}.md"
        skill_file.write_text(content, encoding="utf-8")

    def test_get_skill_text_returns_body(self, skill_storage):
        """Plain Markdown skill file: entire body returned."""
        self._write_skill(skill_storage, "junwin", "test-skill", "Line one\nLine two\n")
        result = skill_storage.get_skill_text("junwin", "test-skill")
        assert result == "Line one\nLine two\n"

    def test_get_skill_text_strips_frontmatter(self, skill_storage):
        """Skill with YAML frontmatter: frontmatter stripped, body returned."""
        content = "---\ntitle: My Skill\n---\nBody text here\n"
        self._write_skill(skill_storage, "junwin", "with-fm", content)
        result = skill_storage.get_skill_text("junwin", "with-fm")
        assert result == "Body text here\n"

    def test_get_skill_text_missing_returns_none(self, skill_storage):
        """Missing skill returns None."""
        result = skill_storage.get_skill_text("junwin", "nonexistent")
        assert result is None

    def test_get_skill_text_missing_account_returns_none(self, skill_storage):
        """Missing account directory returns None."""
        result = skill_storage.get_skill_text("noaccount", "anything")
        assert result is None

    def test_get_skill_text_no_frontmatter_returns_whole(self, skill_storage):
        """File with no frontmatter: entire content returned."""
        content = "Just some text\nNo frontmatter here\n"
        self._write_skill(skill_storage, "junwin", "plain", content)
        result = skill_storage.get_skill_text("junwin", "plain")
        assert result == content

    def test_context_with_imports_loads_skills(self, skill_storage, tmp_path):
        """End-to-end: save context with imports, build prompt, verify skills appear."""
        from src.prompt_builders.prompt_builder import PromptBuilder

        # Write skill files
        self._write_skill(skill_storage, "junwin", "dev-basics", "SKILL: testing in venv")
        self._write_skill(skill_storage, "junwin", "gh-cli", "SKILL: use gh CLI")

        # Write a context with imports
        ctx = ContextState(
            id="testctx",
            account_name="junwin",
            data={
                "tag": "test",
                "imports": ["dev-basics", "gh-cli"],
                "text": "MAIN CONTEXT: project specific info",
            },
            updated_at=datetime.now(timezone.utc),
        )
        skill_storage.save_context(ctx)

        # Build prompt with this context
        pb = PromptBuilder(
            agent_manager=_FakeAgentManager(),
            config=_FakeConfig(),
            storage=skill_storage,
        )
        messages = pb.build_prompt(
            content_text="hello",
            conversation_id="new",
            agent_name="peace",
            account_name="junwin",
            context_name="testctx",
        )

        # Find the context message
        context_msgs = [m for m in messages if "Additional context" in m.get("content", "")]
        assert len(context_msgs) == 1
        context_content = context_msgs[0]["content"]

        # Skills should appear before main context
        assert "SKILL: testing in venv" in context_content
        assert "SKILL: use gh CLI" in context_content
        assert "MAIN CONTEXT" in context_content
        # Skills must precede main context
        skill1_pos = context_content.index("SKILL: testing in venv")
        skill2_pos = context_content.index("SKILL: use gh CLI")
        main_pos = context_content.index("MAIN CONTEXT")
        assert skill1_pos < main_pos
        assert skill2_pos < main_pos

    def test_context_without_imports_works_normally(self, skill_storage, tmp_path):
        """Context without imports field: only main text appears."""
        from src.prompt_builders.prompt_builder import PromptBuilder

        ctx = ContextState(
            id="noimports",
            account_name="junwin",
            data={
                "text": "Only main context",
            },
            updated_at=datetime.now(timezone.utc),
        )
        skill_storage.save_context(ctx)

        pb = PromptBuilder(
            agent_manager=_FakeAgentManager(),
            config=_FakeConfig(),
            storage=skill_storage,
        )
        messages = pb.build_prompt(
            content_text="hello",
            conversation_id="new",
            agent_name="peace",
            account_name="junwin",
            context_name="noimports",
        )

        context_msgs = [m for m in messages if "Additional context" in m.get("content", "")]
        assert len(context_msgs) == 1
        assert "Only main context" in context_msgs[0]["content"]

    def test_context_with_missing_skill_import_continues(self, skill_storage, tmp_path):
        """Missing skill in imports: warning logged, remaining skills + context still load."""
        from src.prompt_builders.prompt_builder import PromptBuilder

        self._write_skill(skill_storage, "junwin", "exists", "SKILL: exists")

        ctx = ContextState(
            id="partial",
            account_name="junwin",
            data={
                "imports": ["exists", "missing-skill"],
                "text": "Main body",
            },
            updated_at=datetime.now(timezone.utc),
        )
        skill_storage.save_context(ctx)

        pb = PromptBuilder(
            agent_manager=_FakeAgentManager(),
            config=_FakeConfig(),
            storage=skill_storage,
        )
        messages = pb.build_prompt(
            content_text="hello",
            conversation_id="new",
            agent_name="peace",
            account_name="junwin",
            context_name="partial",
        )

        context_msgs = [m for m in messages if "Additional context" in m.get("content", "")]
        assert len(context_msgs) == 1
        content = context_msgs[0]["content"]
        assert "SKILL: exists" in content
        assert "Main body" in content


# ---------------------------------------------------------------------------
# Minimal fakes for PromptBuilder tests
# ---------------------------------------------------------------------------

class _FakeAgent:
    system_prompt = "You are peace, a helpful assistant."
    persona = ""
    style_prompt = ""
    max_prompt_conversations = 0


class _FakeAgentManager:
    def get_agent(self, name: str):
        return _FakeAgent()


class _FakeConfig:
    pass
