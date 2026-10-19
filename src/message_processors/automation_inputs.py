"""Compose an automation task's message and attachment arguments.

This preserves the existing consumption of files/file/image_ids from task.meta.
Call only after the RUNNING checkpoint and only when a function processor exists.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.tasklists.task import Task
    from src.tasklists.task_list import TaskList


@dataclass(frozen=True)
class TaskInput:
    message: str
    file_ids: Optional[list[str]]
    image_ids: Optional[list[str]]


def build_task_input(tasklist: TaskList, task: Task) -> TaskInput:
    """Join general instructions, task instructions, then remaining metadata.

    `files` lists win over singular `file`, even when empty. Attachment IDs are
    stringified and removed from nonempty metadata dictionaries in place, as
    before this extraction. Task.files is not used by this existing path.
    """
    message_parts = []

    general_instructions = (getattr(tasklist, "general_instructions", "") or "").strip()
    if general_instructions:
        message_parts.append(general_instructions)

    task_instructions = (task.instructions or "").strip()
    if task_instructions:
        message_parts.append(task_instructions)

    meta = task.meta or {}
    # Extract attachment IDs from meta before building message text.
    file_ids = None
    image_ids = None
    if isinstance(meta, dict):
        # Support both 'files' (list) and 'file' (singular) for file IDs.
        raw_files = meta.pop("files", None)
        raw_file = meta.pop("file", None)
        if isinstance(raw_files, list):
            file_ids = [str(f) for f in raw_files]
        elif raw_file is not None:
            file_ids = [str(raw_file)]

        raw_images = meta.pop("image_ids", None)
        if isinstance(raw_images, list):
            image_ids = [str(i) for i in raw_images]

        for k, v in meta.items():
            key = str(k).strip()
            if not key:
                continue
            message_parts.append(f"{key} = {v}")

    task_message = "\n".join(message_parts).strip()
    return TaskInput(task_message, file_ids, image_ids)
