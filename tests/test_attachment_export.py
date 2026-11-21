"""Regression tests for exporting conversation-owned images to approved directories."""
import json
from pathlib import Path

import pytest
from galet_memory import NewEvent, SqliteEpisodicMemory

from src.handlers.attachments_handler import AttachmentsHandler
from tests.conftest import FakeConfig
from tests.test_reusable_attachments import upload


def run_export(config, memory, ids, *, account="arla", session="chat",
               destination="marie_parie_incoming", collision="rename"):
    return AttachmentsHandler(config).execute(
        {"action": "export", "image_id": "", "offset": 0, "count": 10,
         "image_ids": ids, "destination": destination, "collision": collision},
        account_name=account, conversation_id=session, episodic_store=memory,
    )


def test_export_copies_in_order_and_retains_uploads(tmp_path):
    target = tmp_path / "incoming"
    config = FakeConfig({
        "storage_root_path": str(tmp_path), "storage_namespace": "data",
        "attachment_export_destinations": {"marie_parie_incoming": str(target)},
    })
    first, first_bytes = upload(config, "rose dress.png")
    second, second_bytes = upload(config, "blue-jacket.png")
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        memory.create_session(account_name="arla", session_id="chat")
        memory.append_events(account_name="arla", session_id="chat", events=[
            NewEvent("user", "Make a Reel", "arla",
                     metadata={"image_ids": [first, second]}),
        ])
        result = run_export(config, memory, [first, second])
        assert result["ok"], result
        assert result["count"] == 2
        batch = Path(result["batch_directory"])
        assert batch.parent == target
        assert batch.name.startswith("batch-")
        assert [Path(p["path"]).name for p in result["exported"]] == [
            "rose dress.png", "blue-jacket.png"]
        assert [Path(p["path"]).read_bytes() for p in result["exported"]] == [
            first_bytes, second_bytes]
        assert (tmp_path / "data" / "images" / "arla" / f"{first}.png").exists()
        again = run_export(config, memory, [first, second])
        assert again["ok"]
        assert again["batch_directory"] != str(batch)


def test_export_rejects_cross_conversation_and_account(tmp_path):
    target = tmp_path / "incoming"
    config = FakeConfig({
        "storage_root_path": str(tmp_path), "storage_namespace": "data",
        "attachment_export_destinations": {"marie_parie_incoming": str(target)},
    })
    image_id, _ = upload(config, account="arla")
    john_id, _ = upload(config, account="john")
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        memory.create_session(account_name="arla", session_id="chat")
        memory.create_session(account_name="arla", session_id="other")
        memory.append_events(account_name="arla", session_id="chat", events=[
            NewEvent("user", "Image", "arla", metadata={"image_ids": [image_id]})
        ])
        assert not run_export(config, memory, [image_id], session="other")["ok"]
        assert not run_export(config, memory, [john_id])["ok"]
        assert not run_export(config, memory, [image_id], account="john")["ok"]
        assert not target.exists()


def test_export_collision_policy_and_unsafe_alias(tmp_path):
    target = tmp_path / "incoming"
    config = FakeConfig({
        "storage_root_path": str(tmp_path), "storage_namespace": "data",
        "attachment_export_destinations": {"marie_parie_incoming": str(target)},
    })
    first, _ = upload(config, "same.png")
    second, _ = upload(config, "same.png")
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        memory.create_session(account_name="arla", session_id="chat")
        memory.append_events(account_name="arla", session_id="chat", events=[
            NewEvent("user", "Two pictures", "arla",
                     metadata={"image_ids": [first, second]}),
        ])
        assert not run_export(config, memory, [first, second], collision="fail")["ok"]
        if target.exists():
            assert list(target.iterdir()) == []
        result = run_export(config, memory, [first, second])
        assert result["ok"], result
        files = [x["filename"] for x in result["exported"]]
        assert len(set(files)) == 2
        assert not run_export(config, memory, [first], destination="../bad")["ok"]
        assert not run_export(config, memory, [first, first])["ok"]


def test_export_excludes_unsupported_gif(tmp_path):
    # Upload supports GIF, but media scripts currently accept JPEG/PNG/WebP.
    import io
    from PIL import Image
    from src.http_endpoints.upload_endpoints import post_upload_image_impl
    config = FakeConfig({
        "storage_root_path": str(tmp_path), "storage_namespace": "data",
        "attachment_export_destinations": {"marie_parie_incoming": str(tmp_path / "incoming")},
    })
    output = io.BytesIO()
    Image.new("RGB", (4, 4)).save(output, format="GIF")
    body, status = post_upload_image_impl(config, "arla", output.getvalue(), "moving.gif", "image/gif")
    assert status == 200
    with SqliteEpisodicMemory(tmp_path / "history.sqlite") as memory:
        memory.create_session(account_name="arla", session_id="chat")
        memory.append_events(account_name="arla", session_id="chat", events=[
            NewEvent("user", "Uploaded GIF", "arla", metadata={"image_ids": [body["id"]]})
        ])
        result = run_export(config, memory, [body["id"]])
        assert not result["ok"]


def test_attachment_export_schema_has_approved_destination():
    definition = AttachmentsHandler.tool_def()
    assert "export" in definition["parameters"]["properties"]["action"]["enum"]
    props = definition["parameters"]["properties"]
    assert "destination" in props and "image_ids" in props
