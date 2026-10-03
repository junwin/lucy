from galet_memory import EpisodicEvent, SqliteEpisodicMemory
from scripts.extract_prompt_corpus import build_corpus


def test_extracts_current_database_prompts_with_account_isolation_and_dedup(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'chat.sqlite') as store:
        store.create_session(account_name='alice', agent_name='lucy', session_id='a')
        store.add_events('a', [EpisodicEvent('user', 'hello'), EpisodicEvent('assistant', 'response'),
                               EpisodicEvent('user', 'hello')])
        store.create_session(account_name='bob', agent_name='lucy', session_id='b')
        store.append_event('b', EpisodicEvent('user', 'private'))
        corpus = build_corpus(store, 'alice')
        assert corpus['total_prompts'] == 1
        assert corpus['prompts'][0]['text'] == 'hello'
        assert corpus['prompts'][0]['source'] == 'episodic'
        assert corpus['source_counts']['episodic'] == 2
