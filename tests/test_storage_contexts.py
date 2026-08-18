# ==============================================================================
# FILE: tests/test_storage_contexts.py
# Context/skill storage tests (Issue #115 Context class, #114 skills,
# #120 import resolution lives in JsonFileStorage).
# ==============================================================================

import pytest
from pathlib import Path
from datetime import datetime, timezone

import yaml

from src.storage.models import Context
from src.storage_paths.storage_paths import StoragePaths


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestContexts:
    """Test context/whiteboard operations (in-memory storage fixture)."""

    def test_save_and_load_context(self, storage):
        """Test saving and loading context state."""
        context = Context(
            id="therapy_session_001",
            account_name="junwin",
            extra={
                "goal": "retirement planning",
                "facts": ["retired 2023", "moved to Evanston"],
                "mood": "reflective",
            },
            updated_at=_now(),
        )

        storage.save_context(context)

        retrieved = storage.get_context("junwin", "therapy_session_001")
        assert retrieved is not None
        assert retrieved.id == "therapy_session_001"
        assert retrieved.extra["goal"] == "retirement planning"
        assert "retired 2023" in retrieved.extra["facts"]

    def test_update_context(self, storage):
        """Test updating existing context."""
        context = Context(
            id="ctx_001",
            account_name="junwin",
            extra={"count": 1},
            updated_at=_now(),
        )
        storage.save_context(context)

        context.extra["count"] = 2
        context.extra["new_field"] = "value"
        context.updated_at = _now()
        storage.save_context(context)

        retrieved = storage.get_context("junwin", "ctx_001")
        assert retrieved.extra["count"] == 2
        assert retrieved.extra["new_field"] == "value"

    def test_get_nonexistent_context(self, storage):
        """Test retrieving a context that doesn't exist."""
        result = storage.get_context("junwin", "nonexistent")
        assert result is None

    def test_list_context_names_sorted(self, storage):
        """Lists context names (filename stems) for an account in sorted order."""
        # Create contexts out of lexical order.
        for ctx_id in ["b_ctx", "a_ctx", "c_ctx"]:
            storage.save_context(
                Context(
                    id=ctx_id,
                    account_name="junwin",
                    extra={"id": ctx_id},
                    updated_at=_now(),
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


class TestContextRoundTrip:
    """Round-trip through a real JsonFileStorage (Markdown + YAML frontmatter)."""

    @pytest.fixture
    def skill_storage(self, tmp_path: Path):
        from src.storage.json_file_storage import JsonFileStorage

        storage_root = tmp_path / "lucy_storage"
        storage_root.mkdir()
        paths = StoragePaths(str(storage_root), "data")
        return JsonFileStorage(paths)

    def test_roundtrip_persisted_fields(self, skill_storage):
        """Typed fields survive a save→load round trip; derived fields are reset."""
        ctx = Context(
            id="rt",
            account_name="junwin",
            tag="t",
            imports=["alpha"],
            mandatory_tools=["file_load"],
            search_namespaces=["documents", "external"],
            text="Body text",
            extra={"custom_key": 1},
            updated_at=_now(),
        )
        skill_storage.save_context(ctx)

        loaded = skill_storage.get_context("junwin", "rt")
        assert loaded is not None
        assert loaded.id == "rt"
        assert loaded.account_name == "junwin"
        assert loaded.tag == "t"
        assert loaded.imports == ["alpha"]
        assert loaded.mandatory_tools == ["file_load"]
        assert loaded.search_namespaces == ["documents", "external"]
        assert loaded.text == "Body text"
        assert loaded.extra == {"custom_key": 1}
        # 'alpha' does not exist as a skill -> recorded as missing.
        assert loaded.resolved_skills == []
        assert loaded.missing_imports == ["alpha"]
        assert loaded.resolved_text == "Body text"
        assert loaded.required_tools == ["file_load"]

    def test_legacy_allowed_tools_preserved_in_extra(self, skill_storage):
        """Legacy 'allowed_tools' frontmatter lands in extra (not a typed field)."""
        ctx_dir = skill_storage.storage_paths.contexts / "junwin"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        (ctx_dir / "legacy.md").write_text(
            "---\n"
            "tag: legacy\n"
            "imports:\n"
            "  - alpha\n"
            "allowed_tools:\n"
            "  - web_search_handler\n"
            "mandatory_tools:\n"
            "  - file_load\n"
            "---\n"
            "Body\n",
            encoding="utf-8",
        )

        loaded = skill_storage.get_context("junwin", "legacy")
        assert loaded is not None
        assert loaded.tag == "legacy"
        assert loaded.imports == ["alpha"]
        assert loaded.mandatory_tools == ["file_load"]
        assert loaded.extra == {"allowed_tools": ["web_search_handler"]}
        assert loaded.text == "Body\n"
        assert loaded.missing_imports == ["alpha"]

    def test_no_frontmatter_body_only(self, skill_storage):
        """A context file without frontmatter is treated as body-only."""
        ctx_dir = skill_storage.storage_paths.contexts / "junwin"
        ctx_dir.mkdir(parents=True, exist_ok=True)
        (ctx_dir / "plain.md").write_text("Just a body\n", encoding="utf-8")

        loaded = skill_storage.get_context("junwin", "plain")
        assert loaded is not None
        assert loaded.text == "Just a body\n"
        assert loaded.tag is None
        assert loaded.imports == []
        assert loaded.extra == {}
        assert loaded.resolved_text == "Just a body"
        assert loaded.required_tools == []


class TestSkillLoading:
    """Test skill file loading via JsonFileStorage.get_skill_text / get_skill."""

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

    def test_get_skill_parses_mandatory_tools_and_extra(self, skill_storage):
        """get_skill() returns frontmatter body, mandatory_tools, and extra."""
        content = (
            "---\n"
            "mandatory_tools:\n"
            "  - file_load\n"
            "  - web_search_handler\n"
            "title: My Skill\n"
            "---\n"
            "Body text\n"
        )
        self._write_skill(skill_storage, "junwin", "with-tools", content)
        skill = skill_storage.get_skill("junwin", "with-tools")
        assert skill is not None
        assert skill.name == "with-tools"
        assert skill.text == "Body text\n"
        assert skill.mandatory_tools == ["file_load", "web_search_handler"]
        assert skill.extra == {"title": "My Skill"}


class TestContextImportResolution:
    """Issue #120: get_context() resolves imports into skills + tools.

    Single-level imports only; resolution lives in JsonFileStorage.
    Derived fields (resolved_text, required_tools) are computed, never
    persisted.
    """

    @pytest.fixture
    def skill_storage(self, tmp_path: Path):
        from src.storage.json_file_storage import JsonFileStorage

        storage_root = tmp_path / "lucy_storage"
        storage_root.mkdir()
        paths = StoragePaths(str(storage_root), "data")
        return JsonFileStorage(paths)

    def _write_skill(
        self,
        storage,
        account_name: str,
        skill_name: str,
        body: str,
        *,
        mandatory_tools=None,
        extra_frontmatter=None,
    ):
        """Write a skill file; optional frontmatter is serialized via yaml."""
        skill_dir = storage.storage_paths.skills / account_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / f"{skill_name}.md"
        fm = {}
        if mandatory_tools:
            fm["mandatory_tools"] = list(mandatory_tools)
        if extra_frontmatter:
            fm.update(extra_frontmatter)
        if fm:
            fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
            content = f"---\n{fm_yaml}---\n{body}"
        else:
            content = body
        skill_file.write_text(content, encoding="utf-8")

    def _save_context(self, storage, ctx: Context):
        storage.save_context(ctx)

    def test_resolves_imports_in_order(self, skill_storage):
        """Found skills are appended in import order; tools accumulate."""
        self._write_skill(skill_storage, "junwin", "alpha", "SKILL ALPHA", mandatory_tools=["tool_a"])
        self._write_skill(skill_storage, "junwin", "beta", "SKILL BETA", mandatory_tools=["tool_b"])
        self._save_context(
            skill_storage,
            Context(
                id="c1",
                account_name="junwin",
                imports=["alpha", "beta"],
                text="MAIN BODY",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c1")
        assert loaded is not None
        assert [s.name for s in loaded.resolved_skills] == ["alpha", "beta"]
        assert loaded.missing_imports == []
        assert loaded.resolved_text == (
            "MAIN BODY\n\n## skill: alpha\nSKILL ALPHA\n\n## skill: beta\nSKILL BETA"
        )
        assert loaded.required_tools == ["tool_a", "tool_b"]

    def test_required_tools_order_preserving_dedupe(self, skill_storage):
        """mandatory_tools first, then skills in import order; first wins."""
        self._write_skill(skill_storage, "junwin", "alpha", "A", mandatory_tools=["t_shared", "t_a"])
        self._write_skill(skill_storage, "junwin", "beta", "B", mandatory_tools=["t_shared", "t_b"])
        self._save_context(
            skill_storage,
            Context(
                id="c2",
                account_name="junwin",
                imports=["alpha", "beta"],
                mandatory_tools=["t_ctx", "t_shared"],
                text="M",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c2")
        assert loaded is not None
        assert loaded.required_tools == ["t_ctx", "t_shared", "t_a", "t_b"]

    def test_missing_imports_recorded_and_not_fatal(self, skill_storage):
        """Missing imports land in missing_imports; load still succeeds."""
        self._write_skill(skill_storage, "junwin", "exists", "SKILL EXISTS", mandatory_tools=["t_e"])
        self._save_context(
            skill_storage,
            Context(
                id="c3",
                account_name="junwin",
                imports=["exists", "missing-skill"],
                text="M",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c3")
        assert loaded is not None
        assert [s.name for s in loaded.resolved_skills] == ["exists"]
        assert loaded.missing_imports == ["missing-skill"]
        assert "## skill: exists" in loaded.resolved_text
        assert "missing-skill" not in loaded.resolved_text
        assert loaded.required_tools == ["t_e"]

    def test_resolved_text_strips_skill_frontmatter(self, skill_storage):
        """Only skill bodies appear in resolved_text; frontmatter is stripped."""
        self._write_skill(
            skill_storage,
            "junwin",
            "fm-skill",
            "BODY ONLY",
            mandatory_tools=["t1"],
            extra_frontmatter={"title": "Secret Title", "tags": ["x"]},
        )
        self._save_context(
            skill_storage,
            Context(
                id="c4",
                account_name="junwin",
                imports=["fm-skill"],
                text="M",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c4")
        assert loaded is not None
        assert "BODY ONLY" in loaded.resolved_text
        assert "mandatory_tools" not in loaded.resolved_text
        assert "Secret Title" not in loaded.resolved_text
        assert "tags" not in loaded.resolved_text
        assert loaded.required_tools == ["t1"]

    def test_top_level_imports_only_no_recursion(self, skill_storage):
        """A skill's own imports directive is not resolved (v1, no recursion)."""
        self._write_skill(
            skill_storage,
            "junwin",
            "alpha",
            "SKILL ALPHA",
            extra_frontmatter={"imports": ["beta"]},
        )
        self._write_skill(skill_storage, "junwin", "beta", "SKILL BETA")
        self._save_context(
            skill_storage,
            Context(
                id="c5",
                account_name="junwin",
                imports=["alpha"],
                text="M",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c5")
        assert loaded is not None
        assert [s.name for s in loaded.resolved_skills] == ["alpha"]
        assert "SKILL ALPHA" in loaded.resolved_text
        assert "SKILL BETA" not in loaded.resolved_text

    def test_derived_fields_never_persisted(self, skill_storage):
        """save_context() must not write derived fields back to the file."""
        self._write_skill(skill_storage, "junwin", "alpha", "SKILL ALPHA", mandatory_tools=["t1"])
        self._save_context(
            skill_storage,
            Context(
                id="c6",
                account_name="junwin",
                imports=["alpha"],
                mandatory_tools=["t0"],
                text="M",
                updated_at=_now(),
            ),
        )

        # Load resolves the import, then save the (resolved) object again.
        loaded = skill_storage.get_context("junwin", "c6")
        assert loaded is not None
        assert loaded.resolved_skills and loaded.required_tools == ["t0", "t1"]
        skill_storage.save_context(loaded)

        raw = (
            skill_storage.storage_paths.contexts / "junwin" / "c6.md"
        ).read_text(encoding="utf-8")
        for derived in ("resolved_skills", "missing_imports", "resolved_text", "required_tools"):
            assert derived not in raw, f"derived field '{derived}' leaked into persisted file"
        assert "imports:" in raw  # persisted (declared) field still present
        assert "mandatory_tools:" in raw

    def test_no_imports_backward_compatible(self, skill_storage):
        """Contexts without imports behave exactly as before."""
        self._save_context(
            skill_storage,
            Context(
                id="c7",
                account_name="junwin",
                mandatory_tools=["t0"],
                text="Only body",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c7")
        assert loaded is not None
        assert loaded.resolved_skills == []
        assert loaded.missing_imports == []
        assert loaded.resolved_text == "Only body"
        assert loaded.required_tools == ["t0"]

    def test_skill_without_mandatory_tools_contributes_nothing(self, skill_storage):
        """A skill with no declared tools contributes [] to required_tools."""
        self._write_skill(skill_storage, "junwin", "bare", "BARE BODY")
        self._save_context(
            skill_storage,
            Context(
                id="c8",
                account_name="junwin",
                imports=["bare"],
                text="M",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c8")
        assert loaded is not None
        assert loaded.required_tools == []
        assert "## skill: bare\nBARE BODY" in loaded.resolved_text

    def test_non_string_import_entries_skipped(self, skill_storage):
        """Non-string / empty import entries are skipped, not resolved."""
        self._write_skill(skill_storage, "junwin", "alpha", "SKILL ALPHA")
        self._save_context(
            skill_storage,
            Context(
                id="c9",
                account_name="junwin",
                imports=["alpha", "", 42, None, "  "],
                text="M",
                updated_at=_now(),
            ),
        )

        loaded = skill_storage.get_context("junwin", "c9")
        assert loaded is not None
        assert [s.name for s in loaded.resolved_skills] == ["alpha"]
        assert loaded.missing_imports == []


# ---------------------------------------------------------------------------
# PromptBuilder rendering with storage-resolved contexts (Issue #120)
# ---------------------------------------------------------------------------

class TestPromptBuilderContextRendering:
    """Contexts render through PromptBuilder using storage-side resolution."""

    @pytest.fixture
    def skill_storage(self, tmp_path: Path):
        from src.storage.json_file_storage import JsonFileStorage

        storage_root = tmp_path / "lucy_storage"
        storage_root.mkdir()
        paths = StoragePaths(str(storage_root), "data")
        return JsonFileStorage(paths)

    def _write_skill(self, storage, account_name: str, skill_name: str, content: str):
        skill_dir = storage.storage_paths.skills / account_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / f"{skill_name}.md"
        skill_file.write_text(content, encoding="utf-8")

    def _build_context_content(self, skill_storage, context_name: str) -> str:
        from src.prompt_builders.prompt_builder import PromptBuilder

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
            context_name=context_name,
        )
        context_msgs = [m for m in messages if "Additional context" in m.get("content", "")]
        assert len(context_msgs) == 1
        return context_msgs[0]["content"]

    def test_context_with_imports_processed_but_directives_excluded(self, skill_storage):
        """Imports are resolved (skill bodies under headings); directives must NOT leak."""
        self._write_skill(skill_storage, "junwin", "dev-basics", "SKILL: testing in venv")
        self._write_skill(skill_storage, "junwin", "gh-cli", "SKILL: use gh CLI")

        ctx = Context(
            id="testctx",
            account_name="junwin",
            tag="test",
            imports=["dev-basics", "gh-cli"],
            search_namespaces=["documents", "external"],
            text="MAIN CONTEXT: project specific info",
            extra={"allowed_tools": ["web_search_handler"]},
            updated_at=_now(),
        )
        skill_storage.save_context(ctx)

        content = self._build_context_content(skill_storage, "testctx")

        # Identity header present
        assert "id: testctx" in content
        assert "account_name: junwin" in content
        assert "tag: test" in content
        # Main body present
        assert "MAIN CONTEXT" in content
        # Imported skill bodies ARE resolved and included (with headings)
        assert "## skill: dev-basics" in content
        assert "## skill: gh-cli" in content
        assert "SKILL: testing in venv" in content
        assert "SKILL: use gh CLI" in content
        # Operational directives must NOT leak
        assert "web_search_handler" not in content
        assert "search_namespaces" not in content
        assert "documents" not in content

    def test_context_without_imports_works_normally(self, skill_storage):
        """Context without imports/tag: header (id + account_name) and body only."""
        ctx = Context(
            id="noimports",
            account_name="junwin",
            text="Only main context",
            updated_at=_now(),
        )
        skill_storage.save_context(ctx)

        content = self._build_context_content(skill_storage, "noimports")
        assert "id: noimports" in content
        assert "account_name: junwin" in content
        assert "tag:" not in content
        assert "Only main context" in content

    def test_context_with_missing_skill_import_continues(self, skill_storage):
        """Missing skill imports are skipped; present skills still load."""
        self._write_skill(skill_storage, "junwin", "exists", "SKILL: exists")

        ctx = Context(
            id="partial",
            account_name="junwin",
            imports=["exists", "missing-skill"],
            text="Main body",
            updated_at=_now(),
        )
        skill_storage.save_context(ctx)

        content = self._build_context_content(skill_storage, "partial")
        assert "## skill: exists" in content
        assert "SKILL: exists" in content
        assert "missing-skill" not in content
        assert "id: partial" in content
        assert "account_name: junwin" in content
        assert "Main body" in content


# ---------------------------------------------------------------------------
# Minimal fakes for PromptBuilder tests
# ---------------------------------------------------------------------------

class _FakeAgent:
    system_prompt = "You are peace, a helpful assistant."
    persona = ""
    style_prompt = ""
    max_prompt_conversations = 0
    use_embeddings = False


class _FakeAgentManager:
    def get_agent(self, name: str):
        return _FakeAgent()


class _FakeConfig:
    pass
