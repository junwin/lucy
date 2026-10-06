from unittest.mock import Mock
from galet_memory import CurationService, NewEvent, SqliteEpisodicMemory
from src.handlers.reset_session_handler import ResetSessionHandler


def test_reset_uses_curation_service_account_scope():
    service = Mock()
    handler = ResetSessionHandler(config=Mock())
    result = handler.execute({}, account_name='acct', conversation_id='session-1', curation_service=service)
    assert result == {'action': 'reset_session', 'ok': True}
    service.reset_context.assert_called_once_with(account_name='acct', session_id='session-1')


def test_default_service_is_resolved_lazily(monkeypatch):
    service = Mock()
    monkeypatch.setattr('src.curation.container_factory.get_curation_service', lambda: service)
    result = ResetSessionHandler(Mock()).execute({}, account_name='acct', conversation_id='s')
    assert result['ok']
    service.reset_context.assert_called_once_with(account_name='acct', session_id='s')


def test_reset_preserves_transcript_and_hides_old_context(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'episodic.sqlite') as memory:
        memory.create_session(account_name='acct', session_id='s')
        original = memory.append_event(account_name='acct', session_id='s', event=NewEvent('user', 'old context', 'acct'))
        service = CurationService(memory, Mock())
        handler = ResetSessionHandler(Mock())
        result = handler.execute({}, account_name='acct', conversation_id='s', curation_service=service)
        assert result['ok'], result
        assert memory.get_active_snapshot(account_name='acct', session_id='s').events == ()
        assert memory.get_transcript_snapshot(account_name='acct', session_id='s').events[0].event_id == original.event_id
