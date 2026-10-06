"""Routing can answer simple questions without invoking the agent/prompt builder."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from galet_memory import SqliteEpisodicMemory

from src.message_endpoints.ask_request_handler import AskRequestHandler
from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from tests.test_ask_request_handler import FakeProcessor, FakeProcessorFactory, FakeStorage
from tests.test_skillset_router import make_router, payload


def answer_router(answer='Brasília', **classification):
    return make_router({'kind': 'answer', 'capabilities': [], 'confidence': .99,
                        'answer': answer, **classification})


@pytest.mark.parametrize('streaming', [False, True])
@pytest.mark.parametrize('question,answer', [
    ('What is the capital of Brazil?', 'Brasília.'),
    ('What is 70F in centigrade?', '70°F is approximately 21.1°C.'),
])
def test_direct_answer_uses_one_model_call_saves_history_and_never_constructs_worker(tmp_path, streaming, question, answer):
    with SqliteEpisodicMemory(tmp_path / 'answers.sqlite') as memory:
        router = answer_router(answer)
        router.episodic_store = memory
        storage = FakeStorage()
        factory = Mock()
        handler = AskRequestHandler(router.agent_manager, router.config, storage, factory, memory, router)
        request = payload(question=question, agentName='')
        if streaming:
            events = [json.loads(line.removeprefix('data: ')) for line in handler.handle_streaming(request)]
            assert [event['type'] for event in events] == ['action', 'text', 'done']
            assert events[0]['action'] == 'request_routing'
            routing = events[0]['action_payload']
            assert events[1]['content'] == answer
            session_id = events[2]['conversation_id']
        else:
            status, body = handler.handle(request)
            assert status == 200
            assert body['response'] == answer
            assert body['needs_clarification'] is False
            assert body['run_id'] == body['trace_id']
            routing = body['routing']
            session_id = body['conversation_id']
        assert routing['reason'] == 'direct_answer'
        assert routing['selected_agent'] == 'lucy'
        assert routing['classifier_calls'] == 1
        assert 'direct_response' not in routing
        router.llm_adapter.call_model.assert_called_once()
        factory.get.assert_not_called()
        assert storage.created == []
        session = memory.get_session(account_name='alice', session_id=session_id)
        assert session.metadata["default_agent"] == 'lucy'
        assert [(event.role, event.content) for event in memory.get_active_snapshot(account_name="alice", session_id=session.session_id).events] == [('user', question), ('assistant', answer)]
        assert memory.get_active_snapshot(account_name="alice", session_id=session.session_id).events[1].actor == 'lucy'
        assert memory.get_active_snapshot(account_name="alice", session_id=session.session_id).events[0].metadata['run_id'] == memory.get_active_snapshot(account_name="alice", session_id=session.session_id).events[1].metadata['run_id']


@pytest.mark.parametrize('streaming', [False, True])
def test_direct_answer_preserves_existing_session_identity_and_unrelated_metadata(tmp_path, streaming):
    with SqliteEpisodicMemory(tmp_path / 'existing.sqlite') as memory:
        session = memory.create_session(account_name='alice', context_name='image_tool', metadata={**({
            'project': 'photos', 'routing_dialogue': {'agent': 'lumia', 'expires_at': 10000, 'awaiting_reply': False},
        }), "default_agent": 'lumia'})
        router = answer_router()
        router.clock = lambda: 1000
        router.episodic_store = memory
        factory = Mock()
        handler = AskRequestHandler(router.agent_manager, router.config, FakeStorage(), factory, memory, router)
        request = payload(conversationId=session.session_id, question='What is the capital of Brazil?')
        if streaming:
            list(handler.handle_streaming(request))
        else:
            assert handler.handle(request)[0] == 200
        stored = memory.get_session(account_name='alice', session_id=session.session_id)
        assert stored.metadata["default_agent"] == 'lumia'
        assert stored.context_name == 'image_tool'
        assert stored.metadata == {'project': 'photos', 'default_agent': 'lumia'}
        assert memory.get_active_snapshot(account_name="alice", session_id=stored.session_id).events[-1].content == 'Brasília'
        factory.get.assert_not_called()


@pytest.mark.parametrize('answer,extra', [
    ('', {}), (' ', {}), (None, {}), (123, {}), ('x' * 2001, {}),
    ('Brasília', {'capabilities': ['image-creation']}),
])
def test_malformed_direct_answer_is_not_delivered(answer, extra):
    result = answer_router(answer, **extra).route(payload())
    assert result.reason == 'classifier_failure'
    assert result.direct_response is None
    assert result.clarification


def test_low_confidence_answer_asks_for_guidance():
    result = answer_router(confidence=.2).route(payload())
    assert result.reason == 'uncertain'
    assert result.direct_response is None


@pytest.mark.parametrize('attachments', [{'image_ids': ['image']}, {'file_ids': ['file']}])
def test_attached_content_cannot_take_direct_answer_path(attachments):
    result = answer_router().route(payload(**attachments))
    assert result.direct_response is None
    assert result.reason == 'general'


def test_config_can_disable_direct_answers_without_disabling_auto_routing():
    router = answer_router()
    router.config = SimpleNamespace(get=lambda key, default=None: {'direct_answers_enabled': False} if key == 'request_routing' else default)
    result = router.route(payload(question='What is the capital of Brazil?'))
    assert result.direct_response is None
    assert result.reason == 'general'
    inputs = json.loads(router.llm_adapter.call_model.call_args.kwargs['input'][1]['content'])
    assert inputs['direct_answers_enabled'] is False


@pytest.mark.parametrize('value', [None, 'true', 1])
def test_direct_answer_config_requires_boolean(value):
    router = answer_router()
    router.config = SimpleNamespace(get=lambda key, default=None: {'direct_answers_enabled': value} if key == 'request_routing' else default)
    with pytest.raises(ValueError, match='direct_answers_enabled'):
        router.route(payload())


@pytest.mark.parametrize('overrides', [{'routing': 'explicit'}, {'contextName': 'project'}])
def test_manual_selection_and_explicit_context_still_use_worker(overrides):
    router = answer_router()
    processor = FakeProcessor(FCPResult(text='normal worker', metrics=RunMetrics()))
    handler = AskRequestHandler(router.agent_manager, router.config, FakeStorage(), FakeProcessorFactory(processor), request_router=router)
    status, body = handler.handle(payload(question='What is the capital of Brazil?', **overrides))
    assert status == 200
    assert body['response'] == 'normal worker'
    assert processor.calls
    router.llm_adapter.call_model.assert_not_called()


def test_foreign_session_is_rejected_before_generating_direct_answer(tmp_path):
    with SqliteEpisodicMemory(tmp_path / 'foreign.sqlite') as memory:
        session = memory.create_session(account_name='bob', metadata={"default_agent": 'lucy'})
        router = answer_router()
        router.episodic_store = memory
        handler = AskRequestHandler(router.agent_manager, router.config, FakeStorage(), Mock(), memory, router)
        status, body = handler.handle(payload(conversationId=session.session_id))
        assert status == 400
        router.llm_adapter.call_model.assert_not_called()
        assert memory.get_active_snapshot(account_name='bob', session_id=session.session_id).events == ()


def test_normal_specialist_requests_still_execute_worker():
    router = make_router()
    processor = FakeProcessor(FCPResult(text='image work', metrics=RunMetrics()))
    handler = AskRequestHandler(router.agent_manager, router.config, FakeStorage(), FakeProcessorFactory(processor), request_router=router)
    status, body = handler.handle(payload(question='Create sidecars for these photos'))
    assert status == 200
    assert processor.calls[-1]['primary_agent'].name == 'lumia'
    assert body['routing']['reason'] == 'skillset_match'


def test_classifier_failure_never_delivers_a_direct_answer():
    router = answer_router()
    router.llm_adapter.call_model.side_effect = RuntimeError('offline')
    result = router.route(payload())
    assert result.direct_response is None
    assert result.reason == 'classifier_failure'


def test_direct_answer_does_not_require_advertised_specialists():
    from src.agent import Agent
    from tests.test_skillset_router import Manager
    router = answer_router()
    router.agent_manager = Manager([Agent(name='lucy')])
    result = router.route(payload(question='What is the capital of Brazil?'))
    assert result.direct_response == 'Brasília'
    assert result.reason == 'direct_answer'
    router.llm_adapter.call_model.assert_called_once()
