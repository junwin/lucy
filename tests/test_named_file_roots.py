import json
import sys
from types import SimpleNamespace

import pytest

from src.config_manager import ConfigManager
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2
from src.handlers.patch_apply_handler import PatchApplyHandler
from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.repo_index_handler import RepoIndexHandler
from src.handlers.repo_search_handler import RepoSearchHandler
from src.handlers.galet_adapters import LucyStorageLocationResolver
from src.prompt_builders.prompt_sections import PromptSections
from src.prompt_builders.galet_prompt_builder_adapter import GaletPromptBuilderAdapter
from tests.test_galet_prompt_builder_adapter import (
    _AgentManager, _ProceduralMemory, _RecordingCompiler, _UnusedMemory, _agent,
)


def _config(tmp_path):
    global_file = tmp_path / "config.json"
    global_file.write_text(json.dumps({
        "code_sandbox_path": str(tmp_path / "legacy-sandbox"),
        "storage_root_path": str(tmp_path / "legacy-storage"),
        "storage_namespace": "legacy-namespace",
        "external_roots": {"Pishare": str(tmp_path / "global"),
                           "lucy_data_files": str(tmp_path / "data-store")},
    }))
    local_file = tmp_path / "config.local.json"
    local_file.write_text(json.dumps({"external_roots": {
        "Pishare": str(tmp_path / "local"), "sandbox": str(tmp_path / "work"),
    }}))
    return ConfigManager(str(global_file)), local_file


def test_effective_roots_use_global_local_merge_without_implicit_subdirectories(tmp_path):
    config, _ = _config(tmp_path)
    resolver = LucyStorageLocationResolver(config)
    assert resolver.external_roots() == {
        "Pishare": str(tmp_path / "local"),
        "sandbox": str(tmp_path / "work"),
        "lucy_data_files": str(tmp_path / "data-store"),
    }
    assert resolver.external_root_dir("sandbox") == str(tmp_path / "work")
    with pytest.raises(ValueError, match="Unknown external_root"):
        resolver.external_root_dir("pishare")


def test_file_and_patch_calls_use_effective_alias_and_explicit_account_path(tmp_path):
    config, _ = _config(tmp_path)
    saver = FileSaveHandler2(config)
    args = {"external_root": "Pishare", "path": "namespace/alice/note.txt"}
    result = saver.execute({**args, "file_content": "old\n", "overwrite": True}, account_name="bob")
    assert result["ok"] is True, result
    loaded = json.loads(FileLoadHandler2(config).execute_raw(json.dumps(args), account_name="bob"))
    assert loaded["result"] == "old\n"
    patch = "--- namespace/alice/note.txt\n+++ namespace/alice/note.txt\n@@ -1 +1 @@\n-old\n+new\n"
    handler = PatchApplyHandler(config)
    checked = handler.execute({**args, "patch_content": patch, "check_only": True})
    assert checked["ok"] is True, checked
    assert (tmp_path / "local/namespace/alice/note.txt").read_text() == "old\n"
    applied = handler.execute({**args, "patch_content": patch, "check_only": False})
    assert applied["ok"] is True, applied
    assert (tmp_path / "local/namespace/alice/note.txt").read_text() == "new\n"
    assert not (tmp_path / "local/bob").exists()


@pytest.mark.parametrize("cls", [FileLoadHandler2, FileSaveHandler2, PatchApplyHandler,
                                 CommandExecutionHandler2, RepoIndexHandler, RepoSearchHandler])
def test_lucy_wrappers_expose_named_root_schema(cls):
    parameters = cls.tool_def()["parameters"]
    assert "location" not in parameters["properties"]
    assert "external_root" in parameters["required"]


def test_root_instructions_match_reload_and_only_show_to_file_capable_agents(tmp_path):
    config, local_file = _config(tmp_path)
    agent = SimpleNamespace(allowed_tools=["discover_tools", "activate_tools"])
    text = PromptSections.build_file_root_instructions(config, agent)
    assert str(tmp_path / "local") in text
    assert str(tmp_path / "global") not in text
    assert '"Pishare"' in text
    assert '"lucy_data_files"' in text
    assert "omit location" in text
    assert "No account or namespace is added automatically" in text
    assert PromptSections.build_file_root_instructions(config, SimpleNamespace(allowed_tools=[])) == ""
    local_file.write_text(json.dumps({"external_roots": {"Pishare": str(tmp_path / "reloaded")}}))
    assert config.reload()["config_reloaded"] is True
    current = PromptSections.build_file_root_instructions(config, agent)
    assert str(tmp_path / "reloaded") in current
    assert str(tmp_path / "local") not in current
    assert '"sandbox"' not in current


def test_prompt_compiler_receives_effective_roots_as_budgeted_system_instructions(tmp_path):
    config, _ = _config(tmp_path)
    adapter = GaletPromptBuilderAdapter(
        agent_manager=_AgentManager(_agent(allowed_tools=["file_load"])), config=config,
        storage=SimpleNamespace(), semantic_memory=_UnusedMemory(), episodic_memory=_UnusedMemory(),
        procedural_memory=_ProceduralMemory(), compiler_class=_RecordingCompiler,
    )
    adapter.build_prompt(content_text="Read my note", conversation_id="new", agent_name="peace",
                         account_name="alice")
    request, _, _ = _RecordingCompiler.instance.compile_args
    sections = [section for section in request.system_instructions if "Configured file roots" in section]
    assert len(sections) == 1
    assert str(tmp_path / "local") in sections[0]
    assert str(tmp_path / "global") not in sections[0]


def test_command_and_repository_wrappers_use_root_relative_directories(tmp_path):
    config, _ = _config(tmp_path)
    directory = tmp_path / "work/namespace/alice"
    directory.mkdir(parents=True)
    (directory / "sample.py").write_text("def sample():\n    pass\n")
    command = CommandExecutionHandler2(config).execute({
        "external_root": "sandbox", "working_directory": "namespace/alice",
        "mode": "process", "executable": sys.executable,
        "arguments": ["-c", "import os; print(os.getcwd())"], "script": "", "shell": "none",
        "timeout_seconds": 10, "success_exit_codes": [0],
    }, account_name="bob")
    assert command["ok"] is True, command
    assert command["stdout"].strip() == str(directory)
    index = RepoIndexHandler(config).execute({
        "external_root": "sandbox", "root": "namespace/alice", "operation": "map",
        "query": "", "include_tests": False,
    })
    assert index["ok"] is True, index
    assert index["results"] == ["sample.py"]

