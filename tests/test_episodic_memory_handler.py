"""Lucy wiring of galet-tools' explicit episodic actions."""
import json

from galet_memory import SqliteEpisodicMemory
from galet_tools.tools.episodic_memory_handler import EpisodicMemoryHandler as CanonicalHandler
from src.config_manager import ConfigManager
from src.handlers.episodic_memory_handler import EpisodicMemoryHandler


def _config(tmp_path):
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps({'code_sandbox_path': str(tmp_path)}))
    return ConfigManager(str(config_path))


def _handler(tmp_path):
    return EpisodicMemoryHandler(_config(tmp_path), memory=SqliteEpisodicMemory(tmp_path / 'episodic.sqlite'))


def _base_args(**overrides):
    return overrides


def test_advertises_current_canonical_actions():
    assert EpisodicMemoryHandler.tool_def() == CanonicalHandler.tool_def()
    assert 'get_recent_events' in CanonicalHandler.ACTIONS
    assert 'invalidate_exchange' in CanonicalHandler.ACTIONS
    assert 'recall' not in CanonicalHandler.ACTIONS


def test_round_trip_metadata_events_and_correlations(tmp_path):
    handler = _handler(tmp_path)
    created = handler.execute({'action': 'create_session', 'session_id': 's', 'friendly_name': 'Chat',
                               'metadata': {'default_agent': 'peace'}}, account_name='junwin')
    assert created['ok'], created
    appended = handler.execute({'action': 'append_event', 'session_id': 's', 'event': {
        'role': 'assistant', 'actor': 'peace', 'content': 'remember this',
        'correlation_ids': ['exchange-1']}}, account_name='junwin')
    assert appended['ok'], appended
    assert appended['event']['correlation_ids'] == ['exchange-1']
    recent = handler.execute({'action': 'get_recent_events', 'session_id': 's', 'count': 1}, account_name='junwin')
    assert recent['events'][0]['content'] == 'remember this'
    metadata = handler.execute({'action': 'get_session', 'session_id': 's'}, account_name='junwin')
    assert metadata['session']['friendly_name'] == 'Chat'
    assert 'events' not in metadata['session']


def test_handler_lists_and_deletes_only_account_sessions(tmp_path):
    handler = _handler(tmp_path)
    for account, sid in [('junwin', 'one'), ('junwin', 'two'), ('other', 'foreign')]:
        handler.memory.create_session(account_name=account, session_id=sid)
    listed = handler.execute({'action': 'list_sessions'}, account_name='junwin')
    assert {s['session_id'] for s in listed['sessions']} == {'one', 'two'}
    deleted = handler.execute({'action': 'delete_sessions', 'session_ids': ['one', 'missing', 'one', 'foreign']}, account_name='junwin')
    assert not deleted['ok']
    assert handler.memory.get_session(account_name='junwin', session_id='one') is not None
    deleted = handler.execute({'action': 'delete_sessions', 'session_ids': ['one', 'missing', 'one']}, account_name='junwin')
    assert deleted['session_ids'] == ['one']
    assert handler.memory.get_session(account_name='other', session_id='foreign') is not None
    assert handler.memory.get_session(account_name='junwin', session_id='two') is not None


def test_handler_rejects_empty_bulk_selection_and_legacy_actions(tmp_path):
    handler = _handler(tmp_path)
    assert not handler.execute({'action': 'delete_sessions', 'session_ids': []}, account_name='junwin')['ok']
    assert not handler.execute({'action': 'recall'}, account_name='junwin')['ok']
