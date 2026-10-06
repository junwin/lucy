from galet_memory import NewEvent
from tests.test_episodic_memory_handler import _handler


def test_update_explicit_changes_can_clear_metadata_fields(tmp_path):
    handler = _handler(tmp_path)
    handler.memory.create_session(account_name='junwin', session_id='s', friendly_name='Chat', context_name='project', metadata={'default_agent': 'peace'})
    result = handler.execute({'action': 'update_session', 'session_id': 's', 'changes': {
        'friendly_name': None, 'context_name': None, 'tags': ['x'], 'metadata': {'m': 1}}}, account_name='junwin')
    assert result['ok'], result
    session = handler.memory.get_session(account_name='junwin', session_id='s')
    assert session.friendly_name is None and session.context_name is None
    assert session.tags == ('x',) and session.metadata == {'m': 1}


def test_cross_account_reads_and_writes_are_rejected(tmp_path):
    handler = _handler(tmp_path)
    handler.memory.create_session(account_name='junwin', session_id='s', friendly_name='original')
    for action in ('get_session', 'update_session', 'get_recent_events'):
        args = {'action': action, 'session_id': 's'}
        if action == 'update_session': args['changes'] = {'friendly_name': 'changed'}
        assert not handler.execute(args, account_name='other')['ok']
    assert handler.memory.get_session(account_name='junwin', session_id='s').friendly_name == 'original'


def test_clear_events_is_explicit_and_keeps_metadata(tmp_path):
    handler = _handler(tmp_path)
    handler.memory.create_session(account_name='junwin', session_id='s', metadata={'x': 1})
    handler.memory.append_event(account_name='junwin', session_id='s', event=NewEvent('user', 'hello', 'junwin'))
    result = handler.execute({'action': 'clear_session_events', 'session_id': 's'}, account_name='junwin')
    assert result['ok'], result
    assert result['removed_event_count'] == 1
    assert handler.memory.get_active_snapshot(account_name='junwin', session_id='s').events == ()
    assert handler.memory.get_session(account_name='junwin', session_id='s').metadata == {'x': 1}


def test_invalidate_exchange_hides_events_and_retains_audit(tmp_path):
    handler = _handler(tmp_path)
    handler.memory.create_session(account_name='junwin', session_id='s')
    handler.memory.append_events(account_name='junwin', session_id='s', events=[
        NewEvent('user', 'question', 'junwin', correlation_ids=('exchange',)),
        NewEvent('assistant', 'answer', 'peace', correlation_ids=('exchange',))])
    result = handler.execute({'action': 'invalidate_exchange', 'session_id': 's', 'correlation_id': 'exchange'}, account_name='junwin')
    assert result['ok'] and result['event_count'] == 2
    assert handler.memory.get_active_snapshot(account_name='junwin', session_id='s').events == ()
    assert len(handler.memory.get_audit_snapshot(account_name='junwin', session_id='s').events) == 3


def test_delete_returns_session_id(tmp_path):
    handler = _handler(tmp_path)
    handler.memory.create_session(account_name='junwin', session_id='s')
    result = handler.execute({'action': 'delete_session', 'session_id': 's'}, account_name='junwin')
    assert result['ok'] and result['deleted']
    assert handler.memory.get_session(account_name='junwin', session_id='s') is None
