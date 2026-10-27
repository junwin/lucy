"""Decode successful tool payloads into transport-neutral SSEEvent objects.

This module does not execute tools, enforce limits, modify metrics or advance
the model loop. The loop controls when status events and deliverables are emitted.
"""
import json
from typing import Any, Dict, Generator, List, Tuple

from src.message_processors.fcp_models import _ToolCall
from src.message_processors.sse_events import SSEEvent


def tool_result_events(
    raw_results: List[Tuple[_ToolCall, str]],
    tool_output_items: List[Dict[str, Any]],
) -> Generator[SSEEvent, None, None]:
    """Retain status/ok decoding and output-item call IDs, including zip order."""
    for (tc, raw_text), item in zip(raw_results, tool_output_items):
        call_id = str(item.get("call_id", ""))
        try:
            result_json = json.loads(raw_text)
            ok = result_json.get("ok", True) if isinstance(result_json, dict) else True
            if isinstance(result_json, dict):
                status = result_json.get("status")
            else:
                status = None
        except (json.JSONDecodeError, TypeError):
            ok = True
            status = None

        if status not in ("success", "warning", "error"):
            status = "success" if ok else "error"

        yield SSEEvent(type="tool_result", call_id=call_id, ok=ok, status=status)


def inspect_raw_results(
    raw_results: List[Tuple[_ToolCall, str]],
) -> Generator[SSEEvent, None, None]:
    """Inspect raw tool results for image (PNG/SVG) and action keys.

    Yields SSEEvent objects for any detected keys.
    """
    for _tc, raw_text in raw_results:
        try:
            parsed = json.loads(raw_text) if isinstance(raw_text, str) else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(parsed, dict):
            continue

        if parsed.get("ok") is False:
            continue

        tool_name = getattr(_tc, "name", None) or parsed.get("tool")
        if tool_name == "image_generate" and parsed.get("image_id"):
            yield SSEEvent(
                type="image", format="png", image_id=parsed["image_id"],
                image_ref={"image_id": parsed["image_id"]},
                message_id=f"image:{parsed['image_id']}",
                mime_type=parsed.get("mime_type") or "image/png",
                alt="Generated image",
            )
            continue

        if "action" in parsed:
            yield SSEEvent(
                type="action",
                action=parsed["action"],
                action_payload=parsed.get("action_payload"),
            )

        if "svg" in parsed:
            svg = parsed["svg"]
            if isinstance(svg, dict):
                yield SSEEvent(
                    type="image",
                    format="svg",
                    svg_markup=svg.get("markup"),
                    alt=svg.get("alt") or "",
                    width=svg.get("width"),
                    height=svg.get("height"),
                )

        if "image" in parsed and "svg" not in parsed:
            img = parsed["image"]
            if isinstance(img, dict):
                call_id = getattr(_tc, "call_id", None)
                yield SSEEvent(
                    type="image",
                    format="png",
                    image_url=img.get("url"),
                    alt=img.get("alt"),
                    image_id=img.get("image_id"),
                    image_ref=img if img.get("path") else None,
                    message_id=f"image:{call_id}" if call_id else None,
                )

        if "file" in parsed and tool_name in {"execution_trace", "tasklist_dryrun", "serve_file"}:
            file = parsed["file"]
            if isinstance(file, dict) and file.get("file_id"):
                yield SSEEvent(
                    type="file",
                    file_id=file["file_id"],
                    mime_type=file.get("mime_type") or "application/octet-stream",
                    download_name=file.get("download_name") or "report.yaml",
                    size_bytes=file.get("size_bytes"),
                )

        if "video" in parsed:
            video = parsed["video"]
            if isinstance(video, dict):
                yield SSEEvent(
                    type="video",
                    video_url=video.get("url"),
                    mime_type=video.get("mime_type") or "video/mp4",
                    download_name=video.get("download_name"),
                    video_id=video.get("video_id"),
                    source_image_id=video.get("source_image_id"),
                )
