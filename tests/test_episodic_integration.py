"""Application boundaries against a real explicit-interface backend."""
from types import SimpleNamespace

import pytest
from galet_memory import CurationService, NewEvent, SqliteEpisodicMemory
from src.episodic import list_account_sessions
from src.http_endpoints.chats_endpoints import (
    get_chat_impl, post_chat_message_impl, delete_chat_impl, update_chat_impl,
)
from src.prompt_builders.galet_prompt_builder_adapter import GaletPromptBuilderAdapter
from tests.test_galet_prompt_builder_adapter import _Config, _agent, _AgentManager


@pytest.mark.parametrize('account,expected', [('', 400), ('other', 404)])
def test_chat_operations_require_owning_account(tmp_path, account, expected):
    with SqliteEpisodicMemory(tmp_path / 'episodic.sqlite') as memory:
        memory.create_session(account_name='owner', session_id='s', friendly_name='Original')
        results = [get_chat_impl(memory, 's', account_name=account),
                   post_chat_message_impl(memory, 's', {'role': 'user', 'content': 'private'}, account_name=account),
                   update_chat_impl(memory, 's', {'friendlyName': 'Changed'}, account_name=account),
                   delete_chat_impl(memory, 's', account_name=account)]
        assert all(status == expected for _, status in results)
        assert memory.get_session(account_name='owner', session_id='s').friendly_name == 'Original'
        assert memory.get_active_snapshot(account_name='owner', session_id='s').events == ()


def test_http_changes_can_clear_optional_fields(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'episodic.sqlite') as memory:
        memory.create_session(account_name='owner', session_id='s', context_name='project', friendly_name='Chat')
        _, status = update_chat_impl(memory, 's', {'contextName': None, 'friendlyName': None}, account_name='owner')
        assert status == 200
        session = memory.get_session(account_name='owner', session_id='s')
        assert session.context_name is None and session.friendly_name is None


def test_account_session_listing_crosses_pages_and_honours_limit(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'episodic.sqlite') as memory:
        for index in range(105):
            memory.create_session(account_name='owner', session_id=f's-{index}')
        memory.create_session(account_name='other', session_id='foreign')
        all_sessions = list_account_sessions(memory, 'owner')
        assert len(all_sessions) == 105
        assert len({s.session_id for s in all_sessions}) == 105
        assert len(list_account_sessions(memory, 'owner', 102)) == 102
        assert list_account_sessions(memory, 'owner', 0) == []


def test_lucy_prompt_respects_archive_reset_and_exchange_invalidation(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'episodic.sqlite', digest_search=lambda request: []) as memory:
        memory.create_session(account_name='junwin', session_id='s', metadata={'default_agent': 'peace'})
        original = memory.append_events(account_name='junwin', session_id='s', events=[
            NewEvent('user', 'Previous question', 'junwin', correlation_ids=('old',)),
            NewEvent('assistant', 'Previous answer', 'peace', correlation_ids=('old',))])
        generator = SimpleNamespace(generate=lambda request: 'Archive summary')
        service = CurationService(memory, generator)
        adapter = GaletPromptBuilderAdapter(agent_manager=_AgentManager(_agent(use_embeddings=False)),
            config=_Config(), storage=SimpleNamespace(), semantic_memory=None,
            episodic_memory=memory, procedural_memory=None)
        def prompt():
            return str(adapter.build_prompt(content_text='Next question', conversation_id='s',
                account_name='junwin', agent_name='peace', context_name='none'))
        assert 'Previous answer' in prompt()
        service.archive(account_name='junwin', session_id='s')
        assert 'Archive summary' in prompt() and 'Previous answer' not in prompt()
        service.reset_context(account_name='junwin', session_id='s')
        assert 'Archive summary' not in prompt() and 'Previous answer' not in prompt()
        memory.append_events(account_name='junwin', session_id='s', events=[
            NewEvent('user', 'Mistaken question', 'junwin', correlation_ids=('new',)),
            NewEvent('assistant', 'Mistaken answer', 'other-agent', correlation_ids=('new',))])
        assert 'Mistaken answer' in prompt()
        memory.invalidate_exchange(account_name='junwin', session_id='s', correlation_id='new')
        assert 'Mistaken answer' not in prompt()
        transcript = memory.get_transcript_snapshot(account_name='junwin', session_id='s')
        assert transcript.events[0].event_id == original[0].event_id
        assert all(e.content != 'Mistaken answer' for e in transcript.events)
