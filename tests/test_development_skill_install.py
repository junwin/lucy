"""Install and compile the real shared skill before using slim developer agents."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from galet_memory import FileProceduralMemory, ProceduralLayout, EpisodicMemoryResult

from scripts.install_development_skill import install
from src.agent import AgentManager
from src.prompt_builders.galet_prompt_builder_adapter import GaletPromptBuilderAdapter
from tests.test_galet_prompt_builder_adapter import _Config, _UnusedMemory


@pytest.mark.parametrize('name', ['star', 'colin'])
def test_installed_development_skill_enters_real_agent_prompt(tmp_path, name):
    config = _Config({'storage_root_path': str(tmp_path), 'storage_namespace': 'data'})
    [destination] = install(config, ['junwin'])
    assert destination == tmp_path / 'data' / 'skills' / 'junwin' / 'development.md'
    memory = FileProceduralMemory(tmp_path / 'data', ProceduralLayout.lucy())
    memory.repository.save_context(account_name='junwin', context_name='skinny', text='Development project')
    for skill in ['filepaths', 'loop-prevention']:
        memory.repository.save_skill(account_name='junwin', skill_name=skill, text='Existing instructions: ' + skill)
    manager = AgentManager(str(Path(__file__).parents[1] / 'static/data/agents.json'))
    adapter = GaletPromptBuilderAdapter(
        agent_manager=manager, config=config, storage=SimpleNamespace(),
        semantic_memory=_UnusedMemory(),
        episodic_memory=SimpleNamespace(recall=lambda request: EpisodicMemoryResult()),
        procedural_memory=memory)
    messages = adapter.build_prompt(content_text='Refactor the requested module', conversation_id='new',
                                    agent_name=name, account_name='junwin', context_name='skinny')
    compiled = str(messages)
    assert 'When a supervisor specifies focus files' in compiled
    assert 'If validation fails' in compiled
    assert 'sandbox_execute' in compiled
    assert compiled.count('When a supervisor specifies focus files') == 1
    assert 'Existing instructions: filepaths' in compiled
    assert 'Existing instructions: loop-prevention' in compiled


def test_installer_preserves_custom_skill_and_is_idempotent(tmp_path):
    config = _Config({'storage_root_path': str(tmp_path), 'storage_namespace': 'custom'})
    [destination] = install(config, ['junwin'])
    before = destination.stat().st_mtime_ns
    install(config, ['junwin'])
    assert destination.stat().st_mtime_ns == before
    destination.write_text('---\nname: development\ndescription: Custom\n---\nCustom instructions\n')
    with pytest.raises(FileExistsError, match='Preserving existing skill'):
        install(config, ['junwin'])
    assert destination.read_text().endswith('Custom instructions\n')
    install(config, ['junwin'], overwrite=True)
    assert 'When a supervisor specifies focus files' in destination.read_text()


@pytest.mark.parametrize('account', ['../other', '/tmp/other', '..'])
def test_installer_rejects_account_path_traversal(tmp_path, account):
    config = _Config({'storage_root_path': str(tmp_path)})
    with pytest.raises(ValueError, match='Account names'):
        install(config, [account])
