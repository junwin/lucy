"""Reuse uploaded bytes after reopen, beyond recent history, and across agents."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image
from galet_memory import NewEvent, SqliteEpisodicMemory

from src.handlers.attachments_handler import AttachmentsHandler
from src.handlers.video_generate_handler import VideoGenerateHandler
from src.http_endpoints.upload_endpoints import post_upload_image_impl
from src.message_processors.episodic_recorder import EpisodicRecorder
from src.message_processors.sse_events import SSEEvent
from tests.conftest import FakeAgent, FakeConfig, FakeRegistry, setup_no_tool_calls


def upload(config, filename="blue-jacket.png", account="arla"):
    output = io.BytesIO()
    Image.new("RGB", (12, 12), "blue").save(output, "PNG")
    body, status = post_upload_image_impl(config, account, output.getvalue(), filename, "image/png")
    assert status == 200
    return body["id"], output.getvalue()


def lookup(config, memory, *, account="arla", session="chat", **args):
    return AttachmentsHandler(config).execute(
        {"action": "list", "image_id": "", "count": 10, "offset": 0, **args},
        account_name=account, conversation_id=session, episodic_store=memory,
    )


@pytest.mark.parametrize("streaming", [False, True])
def test_processor_persists_ordered_attachments_without_changing_text(
    tmp_path, make_proc, llm_adapter, streaming,
):
    config = FakeConfig({"storage_root_path": str(tmp_path), "storage_namespace": "data"})
    first, _ = upload(config)
    second, _ = upload(config, "red-jacket.png")
    setup_no_tool_calls(llm_adapter)
    agent = FakeAgent(save_responses=True)
    agent.allowed_tools = ["attachments"]
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        proc = make_proc(config=config, episodic_store=memory)
        params = dict(primary_agent=agent, account={"accountId": "arla"},
                      conversation_id="chat", message="Use these photographs",
                      image_ids=[first, second], file_ids=["document-id"], correlation_id="upload-turn")
        if streaming:
            list(proc.process_message_streaming(**params))
        else:
            proc.process_message(**params)
        events = memory.get_transcript_snapshot(account_name="arla", session_id="chat").events
        user = next(event for event in events if event.kind == "user_message")
        assert user.content == "Use these photographs"
        assert user.metadata["image_ids"] == [first, second]
        assert user.metadata["file_ids"] == ["document-id"]
        assert user.correlation_ids == ("upload-turn",)
        assert "base64" not in json.dumps(user.metadata)
        assert [(i["image_id"], i["position"]) for i in lookup(config, memory)["images"]] == [(first, 1), (second, 2)]


def test_reopen_old_photo_then_generate_two_videos_with_revised_prompts(tmp_path):
    config = FakeConfig({"storage_root_path": str(tmp_path), "storage_namespace": "data"})
    image_id, original_bytes = upload(config)
    database = tmp_path / "history.sqlite"
    with SqliteEpisodicMemory(database) as memory:
        memory.create_session(account_name="arla", session_id="chat")
        EpisodicRecorder(memory).write_user_message(
            SimpleNamespace(account_id="arla", conversation_id="chat", agent_name="lucy"),
            "My blue jacket photograph", correlation_id="original", image_ids=[image_id],
        )
        memory.append_events(account_name="arla", session_id="chat", events=[
            NewEvent("user", f"Unrelated turn {index}", "arla") for index in range(120)
        ])
    with SqliteEpisodicMemory(database) as memory:
        source = lookup(config, memory, action="get", image_id=image_id)["images"][0]
        assert source["filename"] == "blue-jacket.png"
        assert source["correlation_ids"] == ["original"]
        video = VideoGenerateHandler(config)
        api = Mock()
        api.generate_video.return_value = SimpleNamespace(videos=[object()])
        api.download_video.side_effect = lambda result, path: Path(path).write_bytes(b"test-mp4")
        video._video_api = api
        for prompt in ("One gentle step forward", "Turn slightly and smile"):
            result = video.execute({"image_id": source["image_id"], "prompt": prompt,
                                    "duration_seconds": 4, "add_sound": True}, account_name="arla")
            assert result["ok"]
            assert result["video"]["source_image_id"] == image_id
            from jsonschema import validate
            validate(result, video.result_schema())
            from src.message_processors.fcp_loop import LLMLoopRunner
            events = list(LLMLoopRunner._inspect_raw_results([(object(), json.dumps(result))]))
            video_event = next(event for event in events if event.type == "video")
            EpisodicRecorder(memory).write_streaming_event(
                SimpleNamespace(account_id="arla", conversation_id="chat", agent_name="lumia"),
                video_event, correlation_id="video-turn",
            )
        assert api.generate_video.call_count == 2
        calls = api.generate_video.call_args_list
        assert calls[0].kwargs["image_path"] == calls[1].kwargs["image_path"]
        assert Path(calls[0].kwargs["image_path"]).read_bytes() == original_bytes
        assert calls[1].kwargs["prompt"] == "Turn slightly and smile"
        assert lookup(config, memory, action="get", image_id=image_id)["images"][0]["last_video_id"] == result["video_id"]


@pytest.mark.parametrize("streaming", [False, True])
def test_video_source_provenance_survives_both_processor_modes(tmp_path, make_proc, streaming):
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        proc = make_proc(episodic_store=memory)
        proc.loop_runner.run = Mock(return_value=iter([
            SSEEvent(type="video", video_id="video-id", source_image_id="source-id"),
            SSEEvent(type="text", content="Your video is ready"),
        ]))
        params = dict(primary_agent=FakeAgent(save_responses=True), account={"accountId": "arla"},
                      conversation_id="chat", message="Make a video", correlation_id="video-turn")
        if streaming:
            list(proc.process_message_streaming(**params))
        else:
            proc.process_message(**params)
        events = memory.get_transcript_snapshot(account_name="arla", session_id="chat").events
        video = next(event for event in events if event.kind == "generated_video")
        assert video.content["source_image_id"] == "source-id"
        assert video.correlation_ids == ("video-turn",)


def test_scope_generated_images_pagination_and_invalidation(tmp_path):
    config = FakeConfig({"storage_root_path": str(tmp_path), "storage_namespace": "data"})
    first, _ = upload(config)
    second, _ = upload(config, "generated.png")
    foreign, _ = upload(config, account="john")
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        memory.create_session(account_name="arla", session_id="chat")
        memory.create_session(account_name="arla", session_id="other-chat")
        memory.append_events(account_name="arla", session_id="chat", events=[
            NewEvent("user", "Uploaded", "arla", metadata={"image_ids": [first]}, correlation_ids=("original",)),
            NewEvent("assistant", {"image_id": second}, "lumia", kind="generated_image"),
            NewEvent("user", "Forged references", "arla", metadata={"image_ids": [foreign, "/etc/passwd", "../bad"]}),
        ])
        page = lookup(config, memory, count=1)
        assert page["ok"] and page["total"] == 2 and page["next_offset"] == 1
        assert page["images"][0]["origin"] == "generated"
        assert lookup(config, memory, offset=1)["images"][0]["image_id"] == first
        assert lookup(config, memory, account="john")["ok"] is False
        assert lookup(config, memory, session="other-chat", action="get", image_id=first)["ok"] is False
        memory.invalidate_exchange(account_name="arla", session_id="chat", correlation_id="original")
        assert lookup(config, memory, action="get", image_id=first)["ok"] is False
        (tmp_path / "data" / "images" / "arla" / f"{second}.png").unlink()
        assert lookup(config, memory)["images"] == []


@pytest.mark.parametrize("bad", [{"count": 21}, {"count": True}, {"offset": -1}, {"action": "delete"}])
def test_invalid_requests_return_compact_errors(tmp_path, bad):
    assert lookup(FakeConfig(), None, **bad)["ok"] is False


def test_prompt_explains_lookup_and_lazy_selection_keeps_it(make_proc, prompt_builder):
    from src.message_processors.lazy_tool_selection import _apply_rules
    agent = FakeAgent()
    agent.allowed_tools = ["attachments"]
    make_proc().process_message(primary_agent=agent, account={"accountId": "arla"},
                                conversation_id="chat", message="Retry the video with a slower turn")
    system = " ".join(prompt_builder.build_prompt.call_args.kwargs["extra_system_messages"])
    assert "attachments" in system and "several images" in system
    selected, _, _ = _apply_rules("Make a video from the earlier photo", ["video_generate"],
                                 ["video_generate", "attachments"])
    assert selected == ["video_generate", "attachments"]
