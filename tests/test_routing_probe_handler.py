import json
from unittest.mock import Mock

import pytest

from src.handlers.routing_probe_handler import RoutingProbeHandler
from tests.test_skillset_router import make_router, payload


def execute(router, args, **context):
    return RoutingProbeHandler(router.config).execute(
        args, account_name="alice", agent_manager=router.agent_manager,
        llm_adapter=router.llm_adapter, **context)


def test_strict_schema_requires_all_properties_including_nested_cases():
    tool = RoutingProbeHandler.tool_def()
    schema = tool['parameters']
    assert tool['strict']
    assert set(schema['properties']) == set(schema['required'])
    cases = schema['properties']['cases']['items']
    assert set(cases['properties']) == set(cases['required'])
    assert cases['additionalProperties'] is False


def test_batch_uses_real_router_and_does_not_modify_session():
    router = make_router()
    store = Mock()
    store.get_session.return_value = type('Session', (), {'account_name': 'alice', 'metadata': {}})()
    store.get_recent_events.return_value = type('Page', (), {'events': []})()
    result = execute(router, {'cases': [
        {'prompt_text': 'Create a photograph', 'expected_agent': 'lumia'},
        {'prompt_text': 'thanks', 'expected_agent': 'lucy'},
    ], 'conversation_id': 'session'}, episodic_store=store)
    assert result['ok']
    assert result['classifier_calls'] == 1
    assert all(case['matches_expected'] for case in result['results'])
    assert result['results'][0]['diagnostics']['classifier_output']
    store.update_session.assert_not_called()
    store.append_events.assert_not_called()


def test_nullable_defaults_do_not_inherit_calling_agents_context_or_session():
    router = make_router()
    result = execute(router, {'cases': [{'prompt_text': 'Create an image', 'expected_agent': None}],
                             'context_name': None, 'conversation_id': None},
                     context_name='pinned', conversation_id='current')
    assert result['results'][0]['selected_agent'] == 'lumia'
    assert result['classifier_calls'] == 1


def test_model_override_is_local_and_infers_provider():
    router = make_router()
    execute(router, {'cases': [{'prompt_text': 'Create an image'}], 'model': 'test-model'})
    call = router.llm_adapter.call_model.call_args.kwargs
    assert call['model'] == 'test-model'
    assert call['provider'] is None
    assert router.config.get('request_routing') is None


def test_failure_diagnostics_are_bounded_and_batch_continues(caplog):
    router = make_router()
    router.llm_adapter.get_text.return_value = json.dumps({
        'kind': 'specialist', 'capabilities': ['invented'], 'confidence': .9,
        'padding': 'x' * 3000})
    result = execute(router, {'cases': [{'prompt_text': 'Make something'}, {'prompt_text': 'thanks'}]})
    assert result['ok'] is False
    bad, good = result['results']
    assert good['ok']
    diagnostic = bad['diagnostics']
    assert diagnostic['error_stage'] == 'validation'
    assert diagnostic['error'] == 'capabilities contain unknown or non-string labels'
    assert len(diagnostic['classifier_output']) == 2000
    assert diagnostic['output_truncated']
    assert 'stage=validation' in caplog.text
    assert 'output_preview=' in caplog.text


@pytest.mark.parametrize('reply,stage,detail', [
    ('not JSON', 'json_parse', 'Expecting value'),
    ('{"kind":"other","capabilities":[],"confidence":1}', 'validation', 'kind must'),
    ('{"kind":"general","capabilities":[],"confidence":"0.9"}', 'validation', 'confidence must'),
    ('{"kind":"general","capabilities":"writing","confidence":1}', 'validation', 'capabilities must'),
])
def test_precise_errors(reply, stage, detail):
    router = make_router()
    router.llm_adapter.get_text.return_value = reply
    diagnostic = {}
    assert router.route(payload(), diagnostics=diagnostic).reason == 'classifier_failure'
    assert diagnostic['error_stage'] == stage
    assert detail in diagnostic['error']


def test_provider_failure_has_no_output_and_has_exception_type():
    router = make_router()
    router.llm_adapter.call_model.side_effect = TimeoutError('offline')
    diagnostic = {}
    router.route(payload(), diagnostics=diagnostic)
    assert diagnostic['error_stage'] == 'provider_call'
    assert diagnostic['error_type'] == 'TimeoutError'
    assert 'classifier_output' not in diagnostic


def test_foreign_session_is_rejected_before_classifier():
    router = make_router()
    store = Mock()
    store.get_session.return_value = type('Session', (), {'account_name': 'someone_else'})()
    result = execute(router, {'cases': [{'prompt_text': 'Create an image'}],
                             'conversation_id': 'foreign'}, episodic_store=store)
    assert result['ok'] is False
    router.llm_adapter.call_model.assert_not_called()
    store.get_recent_events.assert_not_called()


@pytest.mark.parametrize('cases', [[], [{}], [{'prompt_text': 'x'}] * 11])
def test_rejects_invalid_batches_before_model_calls(cases):
    router = make_router()
    assert execute(router, {'cases': cases})['ok'] is False
    router.llm_adapter.call_model.assert_not_called()
