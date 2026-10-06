"""Specialist continuity across requests, restarts, expiry and changes of work."""
import json
from types import SimpleNamespace

import pytest
from galet_memory import SqliteEpisodicMemory

from src.agent import Agent
from src.message_endpoints.ask_request_handler import AskRequestHandler
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from src.routing.skillset_router import SkillsetRouter
from tests.test_ask_request_handler import FakeProcessor, FakeProcessorFactory, FakeStorage
from tests.test_skillset_router import make_router, payload


@pytest.fixture
def dialogue(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'dialogue.sqlite') as memory:
        session = memory.create_session(account_name='alice', metadata={**({'project': 'photos', 'default_agent': 'lucy'}), "default_agent": 'lucy'})
        router = make_router(agents=[
            Agent(name='lucy'),
            Agent(name='lumia', skillset=['image-processing', 'image-creation']),
            Agent(name='belle', skillset=['writing']),
            Agent(name='colin', skillset=['development']),
            Agent(name='star', skillset=['development']),
        ])
        now = [1000.0]
        router.clock = lambda: now[0]
        router.config = SimpleNamespace(get=lambda key, default=None: {'dialogue_ttl_seconds': 60} if key == 'request_routing' else default)
        router.episodic_store = memory
        request = payload(conversationId=session.session_id)
        first = router.route(request)
        router.remember_dialogue(request, first, session.session_id, 'Which folder should I use?')
        router.llm_adapter.reset_mock()
        yield router, memory, now, request


def classification(router, kind, capabilities=()):
    router.llm_adapter.get_text.return_value = json.dumps({'kind': kind, 'capabilities': list(capabilities), 'confidence': .95})


def state(memory, request):
    return memory.get_session(account_name='alice', session_id=request['conversationId']).metadata


def test_question_reply_stays_with_specialist_even_when_classifier_is_down(dialogue):
    router, memory, now, request = dialogue
    router.llm_adapter.call_model.side_effect = RuntimeError('offline')
    for answer in ['yes', 'ok', 'go ahead']:
        result = router.route({**request, 'question': answer})
        assert result.selected_agent == 'lumia'
        assert result.reason == 'session_continuation'
    router.llm_adapter.call_model.assert_not_called()
    assert state(memory, request)['project'] == 'photos'
    assert memory.get_session(account_name='alice', session_id=request['conversationId']).metadata['default_agent'] == 'lucy'


def test_continuity_survives_router_restart(dialogue):
    router, memory, now, request = dialogue
    restarted = SkillsetRouter(router.agent_manager, router.config, router.llm_adapter, memory, router.clock)
    assert restarted.route({**request, 'question': 'yes'}).selected_agent == 'lumia'


def test_success_renews_inactivity_ttl_and_expiry_routes_again(dialogue):
    router, memory, now, request = dialogue
    now[0] += 50
    reply = router.route({**request, 'question': 'yes'})
    router.remember_dialogue(request, reply, request['conversationId'], 'Done.')
    assert state(memory, request)['routing_dialogue']['expires_at'] == 1110
    now[0] = 1109
    assert router.route({**request, 'question': 'yes'}).selected_agent == 'lumia'
    now[0] = 1110
    classification(router, 'general')
    assert router.route({**request, 'question': 'yes'}).selected_agent == 'lucy'
    inputs = json.loads(router.llm_adapter.call_model.call_args.kwargs['input'][1]['content'])
    assert inputs['active_dialogue'] is None


@pytest.mark.parametrize('ending', ['thanks', 'thank you', 'bye', 'goodbye', "that's all"])
def test_closure_releases_specialist(dialogue, ending):
    router, memory, now, request = dialogue
    result = router.route({**request, 'question': ending})
    assert result.reason == 'dialogue_closed'
    assert result.selected_agent == 'lumia'
    router.remember_dialogue(request, result, request['conversationId'], "You're welcome.")
    assert state(memory, request) == {'project': 'photos', 'default_agent': 'lucy'}
    classification(router, 'general')
    assert router.route({**request, 'question': 'A new question'}).selected_agent == 'lucy'


def test_ok_after_completion_closes_instead_of_approving(dialogue):
    router, memory, now, request = dialogue
    result = router.route({**request, 'question': 'yes'})
    router.remember_dialogue(request, result, request['conversationId'], 'The sidecars are ready.')
    assert router.route({**request, 'question': 'ok'}).reason == 'dialogue_closed'


def test_freeform_answer_is_classified_with_active_dialogue(dialogue):
    router, memory, now, request = dialogue
    classification(router, 'continue')
    result = router.route({**request, 'question': 'Use photography/work/2026/output'})
    assert result.selected_agent == 'lumia'
    assert result.reason == 'session_continuation'
    inputs = json.loads(router.llm_adapter.call_model.call_args.kwargs['input'][1]['content'])
    assert inputs['active_dialogue']['name'] == 'lumia'
    assert inputs['active_dialogue']['awaiting_reply'] is True


def test_shift_to_writing_replaces_specialist(dialogue):
    router, memory, now, request = dialogue
    classification(router, 'specialist', ['writing'])
    result = router.route({**request, 'question': 'Thanks, now write a blog about these images'})
    assert result.selected_agent == 'belle'
    assert result.reason == 'skillset_match'
    router.remember_dialogue(request, result, request['conversationId'], 'What tone would you like?')
    assert state(memory, request)['routing_dialogue']['agent'] == 'belle'
    assert router.route({**request, 'question': 'yes'}).selected_agent == 'belle'


def test_development_shift_asks_for_named_agent_then_keeps_it(dialogue):
    router, memory, now, request = dialogue
    classification(router, 'specialist', ['development'])
    result = router.route({**request, 'question': 'Implement a new API endpoint'})
    assert result.reason == 'ambiguous_specialists'
    assert 'colin, star' in result.clarification
    result = router.route({**request, 'question': 'colin'})
    router.remember_dialogue(request, result, request['conversationId'], 'Which repository?')
    result = router.route({**request, 'question': 'Implement this in Lucy'})
    assert result.selected_agent == 'colin'
    assert result.reason == 'session_continuation'


def test_general_new_task_releases_specialist(dialogue):
    router, memory, now, request = dialogue
    classification(router, 'general')
    result = router.route({**request, 'question': 'What is two plus two?'})
    assert result.selected_agent == 'lucy'
    router.remember_dialogue(request, result, request['conversationId'], 'Four.')
    assert 'routing_dialogue' not in state(memory, request)


def test_no_cross_session_or_account_affinity(dialogue):
    router, memory, now, request = dialogue
    other = memory.create_session(account_name='alice', metadata={"default_agent": 'lucy'})
    classification(router, 'general')
    assert router.route({**request, 'conversationId': other.session_id, 'question': 'yes'}).selected_agent == 'lucy'
    with pytest.raises(ValueError, match='does not belong'):
        router.route({**request, 'accountName': 'bob', 'question': 'ok'})
    assert state(memory, request)['routing_dialogue']['agent'] == 'lumia'


def test_manual_selection_releases_affinity_and_preserves_metadata(dialogue):
    router, memory, now, request = dialogue
    router.remember_dialogue({**request, 'routing': 'explicit'}, None, request['conversationId'])
    assert state(memory, request) == {'project': 'photos', 'default_agent': 'lucy'}


def test_no_continuation_without_live_affinity(dialogue):
    router, memory, now, request = dialogue
    now[0] += 60
    classification(router, 'continue')
    result = router.route({**request, 'question': 'Use the output folder'})
    assert result.reason == 'classifier_failure'
    assert result.clarification


@pytest.mark.parametrize('ttl', [-1, float('nan'), True, '60'])
def test_invalid_ttl_is_rejected(dialogue, ttl):
    router, memory, now, request = dialogue
    router.config = SimpleNamespace(get=lambda key, default=None: {'dialogue_ttl_seconds': ttl} if key == 'request_routing' else default)
    with pytest.raises(ValueError, match='dialogue_ttl_seconds'):
        router.route(request)


def test_zero_ttl_disables_affinity(dialogue):
    router, memory, now, request = dialogue
    router.config = SimpleNamespace(get=lambda key, default=None: {'dialogue_ttl_seconds': 0} if key == 'request_routing' else default)
    classification(router, 'general')
    result = router.route({**request, 'question': 'yes'})
    assert result.selected_agent == 'lucy'
    router.remember_dialogue(request, result, request['conversationId'], 'Hello.')
    assert 'routing_dialogue' not in state(memory, request)


@pytest.mark.parametrize('streaming', [False, True])
def test_ask_persists_affinity_before_done_and_routes_next_reply(tmp_path, streaming):
    with SqliteEpisodicMemory(tmp_path / 'ask.sqlite') as memory:
        router = make_router()
        router.episodic_store = memory
        class Processor(FakeProcessor):
            def process_message_streaming(self, **kwargs):
                self.calls.append(kwargs)
                yield 'data: {"type":"text","content":"Which folder should I use?"}\n\n'
                yield 'data: {"type":"done"}\n\n'
        processor = Processor(FCPResult(text='Which folder should I use?', metrics=RunMetrics()))
        handler = AskRequestHandler(router.agent_manager, router.config, FakeStorage(), FakeProcessorFactory(processor), memory, router)
        if streaming:
            for line in handler.handle_streaming(payload()):
                if json.loads(line.removeprefix('data: ')).get('type') == 'done':
                    session_id = processor.calls[-1]['conversation_id']
                    assert memory.get_session(account_name='alice', session_id=session_id).metadata['routing_dialogue']['agent'] == 'lumia'
        else:
            status, body = handler.handle(payload())
            assert status == 200
            session_id = body['conversation_id']
            assert memory.get_session(account_name='alice', session_id=session_id).metadata['routing_dialogue']['agent'] == 'lumia'
        router.llm_adapter.call_model.side_effect = RuntimeError('offline')
        reply = payload(conversationId=session_id, question='ok')
        if streaming:
            list(handler.handle_streaming(reply))
        else:
            assert handler.handle(reply)[0] == 200
        assert processor.calls[-1]['primary_agent'].name == 'lumia'
        assert processor.calls[-1]['conversation_id'] == session_id


@pytest.mark.parametrize('streaming', [False, True])
def test_execution_failure_does_not_create_affinity(tmp_path, streaming):
    with SqliteEpisodicMemory(tmp_path / 'failed.sqlite') as memory:
        router = make_router()
        router.episodic_store = memory
        class Processor(FakeProcessor):
            def process_message_streaming(self, **kwargs):
                self.calls.append(kwargs)
                yield 'data: {"type":"error","message":"offline"}\n\n'
                yield 'data: {"type":"done"}\n\n'
        processor = Processor(FCPResult(text='Failed.', metrics=RunMetrics(success=False)))
        handler = AskRequestHandler(router.agent_manager, router.config, FakeStorage(), FakeProcessorFactory(processor), memory, router)
        if streaming:
            list(handler.handle_streaming(payload()))
        else:
            handler.handle(payload())
        session_id = processor.calls[-1]['conversation_id']
        assert 'routing_dialogue' not in memory.get_session(account_name='alice', session_id=session_id).metadata


def test_configured_catalog_can_shift_from_image_work_to_writing(dialogue):
    from pathlib import Path
    from src.agent import AgentManager
    router, memory, now, request = dialogue
    router.agent_manager = AgentManager(str(Path(__file__).parents[1] / 'static/data/agents.json'))
    classification(router, 'specialist', ['writing'])
    result = router.route({**request, 'question': 'Now write a blog about these pictures'})
    assert result.selected_agent == 'belle'
    assert result.capabilities == ('writing',)
