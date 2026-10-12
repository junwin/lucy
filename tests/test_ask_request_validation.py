"""Shared request contract, including JSON/SSE differences retained by #278."""

import json
from unittest.mock import Mock

import pytest

from src.message_processors.function_calling_processor import FCPResult
from src.message_processors.run_metrics import RunMetrics
from tests.test_ask_request_handler import FakeProcessor, make_agent, make_handler, make_payload


class StreamingProcessor(FakeProcessor):
    def process_message_streaming(self, **kwargs):
        self.calls.append(kwargs)
        yield 'data: {"type":"done"}\n\n'


def events(handler, payload):
    return [json.loads(line.removeprefix('data: ')) for line in handler.handle_streaming(payload)]


@pytest.mark.parametrize('overrides', [
    {'question': ''}, {'question': None}, {'agentName': ''}, {'accountName': ''},
])
@pytest.mark.parametrize('streaming', [False, True])
def test_required_fields_still_reject_before_processor(overrides, streaming):
    processor = StreamingProcessor(FCPResult(text='ok', metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())
    request = make_payload(**overrides)
    if streaming:
        result = events(handler, request)
        assert [item['type'] for item in result] == ['error', 'done']
        assert result[0]['message'] == 'Missing question, agentName, or accountName'
        assert 'conversation_id' not in result[-1]
    else:
        assert handler.handle(request) == (400, {'error': 'Missing question, agentName, or accountName'})
    assert processor.calls == []


@pytest.mark.parametrize('overrides', [
    {'question': '', 'image_ids': ['img-1']},
    {'question': '', 'file_ids': ['file-1']},
])
@pytest.mark.parametrize('streaming', [False, True])
def test_empty_question_with_attachments_reaches_processor(overrides, streaming):
    processor = StreamingProcessor(FCPResult(text='ok', metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())
    request = make_payload(**overrides)
    if streaming:
        assert events(handler, request) == [{'type': 'done'}]
    else:
        assert handler.handle(request)[0] == 200
    assert len(processor.calls) == 1
    assert processor.calls[0]['message'] == ''


@pytest.mark.parametrize('streaming', [False, True])
def test_normalized_inputs_keep_legacy_precedence_and_attachment_identity(streaming):
    processor = StreamingProcessor(FCPResult(text='ok', metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())
    processor.context_type = None
    images, files = ['image-1'], ['file-1']
    request = make_payload(
        agentName='LUCY', accountName='ALICE', conversationId='existing',
        selectType='obsidian', contextType='episodic', contextName='  project  ',
        image_ids=images, file_ids=files,
    )
    if streaming:
        assert events(handler, request)[-1]['type'] == 'done'
    else:
        assert handler.handle(request)[0] == 200
    call = processor.calls[0]
    assert call['account'] == {'accountId': 'alice'}
    assert call['context_name'] == 'project'
    assert processor.context_type == 'obsidian'
    assert call['image_ids'] is images
    assert call['file_ids'] is files
    assert request['agentName'] == 'LUCY'
    assert request['contextName'] == '  project  '


@pytest.mark.parametrize('streaming', [False, True])
def test_context_backfill_failure_preserves_transport_behavior(streaming):
    processor = StreamingProcessor(FCPResult(text='ok', metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())
    handler.episodic_store = Mock()
    handler.episodic_store.get_session.side_effect = RuntimeError('storage unavailable')
    request = make_payload(conversationId='existing', contextName='project')
    if streaming:
        assert events(handler, request) == [{'type': 'done'}]
        assert len(processor.calls) == 1
    else:
        assert handler.handle(request) == (500, {'error': 'Failed to resolve or create session'})
        assert processor.calls == []


@pytest.mark.parametrize('streaming', [False, True])
def test_new_session_failure_preserves_transport_error_message(streaming):
    processor = StreamingProcessor(FCPResult(text='ok', metrics=RunMetrics()))
    handler = make_handler(processor, make_agent())
    handler.episodic_store = Mock()
    handler.episodic_store.create_session.side_effect = RuntimeError('storage unavailable')
    if streaming:
        result = events(handler, make_payload())
        assert [item['type'] for item in result] == ['error', 'done']
        assert result[0]['message'] == 'Failed to create chat session'
    else:
        assert handler.handle(make_payload()) == (500, {'error': 'Failed to resolve or create session'})
    assert processor.calls == []
