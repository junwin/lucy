from tests.episodic_fixtures import event_fixture
from galet_memory import SqliteEpisodicMemory
from scripts.extract_prompt_corpus import build_corpus


def test_extracts_current_database_prompts_with_account_isolation_and_dedup(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'chat.sqlite') as store:
        store.create_session(account_name='alice', session_id='a', metadata={"default_agent": 'lucy'})
        store.append_events(account_name='alice', session_id='a', events=[event_fixture('user', 'hello'), event_fixture('assistant', 'response'),
                               event_fixture('user', 'hello')])
        store.create_session(account_name='bob', session_id='b', metadata={"default_agent": 'lucy'})
        store.append_event(account_name='bob', session_id='b', event=event_fixture('user', 'private'))
        corpus = build_corpus(store, 'alice')
        assert corpus['total_prompts'] == 1
        assert corpus['prompts'][0]['text'] == 'hello'
        assert corpus['prompts'][0]['source'] == 'episodic'
        assert corpus['source_counts']['episodic'] == 2
