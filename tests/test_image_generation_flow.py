"""Basic image use case through generation, FCP transport and saved history."""
import base64
import io
import json
from unittest.mock import Mock
from uuid import uuid4

from PIL import Image
from galet.imagegen_dto import ImageGenResponse, ImageResult
from galet_memory import SqliteEpisodicMemory

from src.handlers.image_generate_handler import ImageGenerateHandler
from src.handlers.serve_image_handler import ServeImageHandler
from src.http_endpoints.chats_endpoints import get_chat_impl
from src.message_processors.fcp_models import _ToolCall
from src.message_processors.fcp_loop import LLMLoopRunner
from tests.conftest import FakeAgent, FakeConfig, FakeRegistry, setup_tool_then_text


def test_generate_show_and_reopen_without_bytes_in_model_or_history(
    tmp_path, make_proc, llm_adapter,
):
    config = FakeConfig({"storage_root_path": str(tmp_path), "storage_namespace": "data",
                         "max_tool_result_chars": 1000})
    handler = ImageGenerateHandler(config)
    png = io.BytesIO()
    Image.new('RGB', (1536, 1536), 'green').save(png, format='PNG')
    handler._image_api = Mock()
    handler._image_api.generate_image.return_value = ImageGenResponse(
        [ImageResult(b64_json=base64.b64encode(png.getvalue()).decode())], model='gpt-image-1')
    registry = FakeRegistry({'image_generate': handler}, [handler.tool_def()])
    setup_tool_then_text(llm_adapter, tool_name='image_generate',
                         tool_args=json.dumps({'prompt': 'A green hill', 'model': 'gpt-image-1'}),
                         final_text='Here is your image.')
    # A tool-call iteration has no user-facing text; the following turn confirms it.
    llm_adapter.get_text.side_effect = ['', 'Here is your image.', 'Here is your image.']
    agent = FakeAgent(save_responses=True)
    agent.allowed_tools = ['image_generate']
    session_id = str(uuid4())
    with SqliteEpisodicMemory(tmp_path / 'history.sqlite') as memory:
        proc = make_proc(config=config, registry=registry, episodic_store=memory)
        events = [json.loads(line.removeprefix('data: ').strip()) for line in
                  proc.process_message_streaming(primary_agent=agent, account={'accountId': 'john'},
                      message='Create an image of a hill', conversation_id=session_id)]
        images = [event for event in events if event['type'] == 'image']
        assert len(images) == 1
        image = images[0]
        assert image['image_url'].startswith('data:image/png;base64,')
        assert [event['content'] for event in events if event['type'] == 'text'] == ['Here is your image.']
        preview = base64.b64decode(image['image_url'].split(',', 1)[1])
        assert Image.open(io.BytesIO(preview)).size == (1024, 1024)
        model_result = llm_adapter.call_model.call_args_list[1].kwargs['input'][0]['output']
        assert len(model_result) < 1000 and 'base64' not in model_result
        assert json.loads(model_result)['image_id'] == image['image_id']
        history = memory.get_active_snapshot(account_name='john', session_id=session_id).events
        assert 'base64' not in json.dumps([event.content for event in history])
        saved = [event for event in history if event.kind == 'generated_image']
        assert len(saved) == 1 and saved[0].content['image_id'] == image['image_id']
        reopened, status = get_chat_impl(memory, session_id, config=config, account_name="john")
        assert status == 200
        payload = json.loads(next(m['content'] for m in reopened['messages'] if m['kind'] == 'generated_image'))
        assert payload['image_id'] == image['image_id']
        assert payload['image_url'].startswith('/download/image/')
        assert 'base64' not in json.dumps(reopened)
    handler._image_api.generate_image.assert_called_once()


def test_serve_image_uses_same_preview_boundary(tmp_path):
    from src.message_processors.image_delivery import image_event_for_browser
    config = FakeConfig({'storage_root_path': str(tmp_path), 'storage_namespace': 'data'})
    directory = tmp_path / 'data'
    directory.mkdir()
    Image.new('RGB', (40, 40), 'red').save(directory / 'photo.png')
    handler = ServeImageHandler(config)
    result = handler.execute({'location': 'storage', 'path': 'photo.png'}, account_name='john')
    assert result['ok'] and 'base64' not in json.dumps(result)
    events = list(LLMLoopRunner._inspect_raw_results([
        (_ToolCall(name='serve_image', call_id='serve-1', arguments_raw='{}'), json.dumps(result))]))
    assert len(events) == 1
    assert image_event_for_browser(events[0], config, 'john').image_url.startswith('data:image/png;base64,')


def test_duplicate_image_events_are_delivered_and_saved_once(tmp_path, make_proc):
    from src.message_processors.sse_events import SSEEvent
    from tests.test_image_download import saved_image
    image_id, _ = saved_image(tmp_path)
    config = FakeConfig({'storage_root_path': str(tmp_path), 'storage_namespace': 'data'})
    event = SSEEvent(type='image', image_id=image_id, format='png', message_id=f'image:{image_id}')
    session_id = str(uuid4())
    with SqliteEpisodicMemory(tmp_path / 'history.sqlite') as memory:
        proc = make_proc(config=config, episodic_store=memory)
        proc.loop_runner.run = Mock(return_value=iter([event, event, SSEEvent(type='done')]))
        wire = list(proc.process_message_streaming(primary_agent=FakeAgent(save_responses=True),
            account={'accountId': 'john'}, message='Show the image', conversation_id=session_id))
        assert sum(json.loads(line.removeprefix('data: ').strip())['type'] == 'image' for line in wire) == 1
        assert sum(event.kind == 'generated_image' for event in memory.get_active_snapshot(account_name='john', session_id=session_id).events) == 1


def test_serving_account_image_path_cannot_bypass_account_check(tmp_path):
    from tests.test_image_download import saved_image
    image_id, _ = saved_image(tmp_path)
    config = FakeConfig({'storage_root_path': str(tmp_path), 'storage_namespace': 'data'})
    result = ServeImageHandler(config).execute({'location': 'storage',
        'path': f'./images/john/{image_id}.png'}, account_name='arla')
    assert not result['ok']
