import base64
import json
from src.message_processors.image_delivery import image_result_for_model
from src.message_processors.image_delivery import image_event_for_browser
from src.message_processors.sse_events import SSEEvent
from test_image_download import Config, saved_image


def test_inline_transport_leaves_original_reference_compact(tmp_path):
    image_id, image = saved_image(tmp_path)
    url = f"/download/image/{image_id}?accountName=john"
    original = SSEEvent(type="image", format="png", image_url=url, alt="Dog")
    wire = image_event_for_browser(original, Config(tmp_path), "john")
    assert wire is not original
    assert wire.image_url == "data:image/png;base64," + base64.b64encode(image.read_bytes()).decode()
    assert original.image_url == url
    assert wire.alt == "Dog"
    assert "data:image/png;base64," in wire.to_sse()


def test_other_account_and_missing_files_do_not_deliver_bytes(tmp_path):
    image_id, image = saved_image(tmp_path)
    event = SSEEvent(type="image", image_url=f"/download/image/{image_id}?accountName=john")
    assert image_event_for_browser(event, Config(tmp_path), "arla").image_url is None
    image.unlink()
    assert image_event_for_browser(event, Config(tmp_path), "john").image_url is None


def test_external_and_existing_inline_events_are_untouched(tmp_path):
    for url in ["https://example.org/download/image/a", "data:image/png;base64,YQ=="]:
        event = SSEEvent(type="image", image_url=url)
        assert image_event_for_browser(event, Config(tmp_path), "john") is event
    event = SSEEvent(type="text", content="hello")
    assert image_event_for_browser(event, Config(tmp_path), "john") is event


def test_traversal_cannot_read_server_files(tmp_path):
    event = SSEEvent(type="image", image_url="/download/image/../../etc/passwd")
    assert image_event_for_browser(event, Config(tmp_path), "john").image_url is None


def test_model_response_has_reference_without_presentation_urls():
    raw = json.dumps({"ok": True, "image_id": "id", "path": "images/john/id.png", "image": {"url": "/download/image/id"}, "download_url": "/download/image/id"})
    result = json.loads(image_result_for_model("image_generate", raw))
    assert result["image_id"] == "id"
    assert "image" not in result and "download_url" not in result
    assert "image" in json.loads(raw)
    assert image_result_for_model("other_tool", raw) == raw
    assert image_result_for_model("image_generate", '{"ok": false}') == '{"ok": false}'
