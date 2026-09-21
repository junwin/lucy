import json

from src.message_processors.fcp_loop import LLMLoopRunner
from src.message_processors.sse_events import SSEEvent


def test_video_event_serializes_for_sse() -> None:
    event = SSEEvent(
        type="video",
        video_url="/download/video/123?accountName=arla",
        mime_type="video/mp4",
        download_name="fashion-reel.mp4",
        video_id="123",
    )

    payload = json.loads(event.to_sse()[6:-2])
    assert payload == {
        "type": "video",
        "video_url": "/download/video/123?accountName=arla",
        "mime_type": "video/mp4",
        "download_name": "fashion-reel.mp4",
        "video_id": "123",
    }


def test_video_tool_result_becomes_video_event() -> None:
    raw_results = [
        (
            object(),
            json.dumps(
                {
                    "ok": True,
                    "video": {
                        "url": "/download/video/123?accountName=arla",
                        "mime_type": "video/mp4",
                        "download_name": "fashion-reel.mp4",
                        "video_id": "123",
                    },
                }
            ),
        )
    ]

    events = list(LLMLoopRunner._inspect_raw_results(raw_results))

    assert len(events) == 1
    assert events[0].type == "video"
    assert events[0].video_url == "/download/video/123?accountName=arla"
    assert events[0].mime_type == "video/mp4"
    assert events[0].download_name == "fashion-reel.mp4"
    assert events[0].video_id == "123"
