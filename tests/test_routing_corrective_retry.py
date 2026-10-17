"""Malformed routing output gets one correction, never an invented confidence."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.test_skillset_router import make_router, payload


def with_active_dialogue(router):
    store = Mock()
    store.get_session.return_value = SimpleNamespace(account_name='alice', metadata={
        'routing_dialogue': {'agent': 'lumia', 'expires_at': 2000, 'awaiting_reply': True}})
    store.get_recent_events.return_value = SimpleNamespace(events=[])
    router.episodic_store = store
    router.clock = lambda: 1000
    return store


def test_missing_confidence_continuation_recovers_and_preserves_first_failure(caplog):
    router = make_router()
    store = with_active_dialogue(router)
    router.llm_adapter.get_text.side_effect = [
        '{"kind": "continue", "capabilities": []}',
        '{"kind": "continue", "capabilities": [], "confidence": 0.95}',
    ]
    diagnostics = {}
    with caplog.at_level('INFO'):
        result = router.route(payload(question='Use the second photograph instead', conversationId='session'),
                              diagnostics=diagnostics)
    assert result.reason == 'session_continuation'
    assert result.selected_agent == 'lumia'
    assert result.classifier_calls == 2
    assert 'error' not in diagnostics
    assert diagnostics['attempts'][0]['error_stage'] == 'validation'
    assert 'confidence' in diagnostics['attempts'][0]['error']
    assert 'error' not in diagnostics['attempts'][1]
    assert 'corrective_retry' in caplog.text
    assert 'recovered=True' in caplog.text
    first, second = [c.kwargs for c in router.llm_adapter.call_model.call_args_list]
    assert first['model'] == second['model']
    assert first['provider'] == second['provider']
    assert second['input'][:2] == first['input']
    assert len(second['input']) == 4
    assert 'confidence must' in second['input'][-1]['content']
    assert 'Every result MUST include kind, capabilities and confidence' in first['input'][0]['content']
    store.update_session.assert_not_called()
    store.append_events.assert_not_called()


@pytest.mark.parametrize('invalid', [
    'not JSON', '[]', '{}',
    '{"kind":[],"capabilities":[],"confidence":0.9}',
    '{"kind":"specialist","capabilities":["unknown"],"confidence":0.9}',
    '{"kind":"general","capabilities":[],"confidence":"0.9"}',
    '{"kind":"general","capabilities":[],"confidence":true}',
    '{"kind":"general","capabilities":[],"confidence":2}',
    '{"kind":"continue","capabilities":[]}',
])
def test_malformed_result_gets_exactly_one_correction(invalid):
    router = make_router()
    router.llm_adapter.get_text.side_effect = [invalid, json.dumps({
        'kind': 'specialist', 'capabilities': ['image-creation'], 'confidence': .95})]
    result = router.route(payload())
    assert result.selected_agent == 'lumia'
    assert result.classifier_calls == 2
    assert router.llm_adapter.call_model.call_count == 2


def test_twice_missing_confidence_still_fails_without_default():
    router = make_router()
    router.llm_adapter.get_text.return_value = '{"kind":"continue","capabilities":[]}'
    diagnostic = {}
    result = router.route(payload(), diagnostics=diagnostic)
    assert result.reason == 'classifier_failure'
    assert result.clarification
    assert result.classifier_calls == 2
    assert len(diagnostic['attempts']) == 2
    assert all('confidence' in attempt['error'] for attempt in diagnostic['attempts'])


def test_provider_failure_does_not_trigger_application_retry():
    router = make_router()
    router.llm_adapter.call_model.side_effect = TimeoutError('offline')
    result = router.route(payload())
    assert result.reason == 'classifier_failure'
    assert result.classifier_calls == 1
    router.llm_adapter.call_model.assert_called_once()


def test_provider_failure_on_correction_stops_and_clears_stale_output():
    router = make_router()
    router.llm_adapter.call_model.side_effect = [object(), TimeoutError('offline')]
    router.llm_adapter.get_text.return_value = 'not JSON'
    diagnostic = {}
    result = router.route(payload(), diagnostics=diagnostic)
    assert result.reason == 'classifier_failure'
    assert result.classifier_calls == 2
    assert diagnostic['attempts'][0]['error_stage'] == 'json_parse'
    assert diagnostic['attempts'][1]['error_stage'] == 'provider_call'
    assert 'classifier_output' not in diagnostic['attempts'][1]


@pytest.mark.parametrize('kind,confidence', [('general', .9), ('general', .2), ('clarify', .9)])
def test_valid_or_uncertain_output_does_not_retry(kind, confidence):
    router = make_router({'kind': kind, 'capabilities': [], 'confidence': confidence})
    result = router.route(payload())
    assert result.reason in {'general', 'uncertain'}
    assert result.classifier_calls == 1
    router.llm_adapter.call_model.assert_called_once()


def test_continue_without_active_dialogue_is_not_accepted_after_retry():
    router = make_router({'kind': 'continue', 'capabilities': [], 'confidence': .95})
    assert router.route(payload()).reason == 'classifier_failure'
    assert router.llm_adapter.call_model.call_count == 2
