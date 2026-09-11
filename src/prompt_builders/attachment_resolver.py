from __future__ import annotations

import base64
import glob
import logging
import os
from typing import Any, Dict, List, Optional

from src.config_manager import ConfigManager


class AttachmentResolver:
    """Resolve prompt image/file IDs into provider-neutral content parts."""

    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    def resolve(
        self,
        *,
        account_name: str,
        image_ids: Optional[List[str]],
        file_ids: Optional[List[str]],
        agent_allowed_tools: Optional[List[str]] = None,
        supports_images: bool = True,
    ) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []
        images_dir = self.build_images_dir()
        any_image_marked = False

        for img_id in (image_ids or []):
            try:
                img_path = self.find_image_file(images_dir, account_name, img_id)
                if img_path is None:
                    logging.warning(
                        "PromptBuilder: image_id=%s not found for account=%s; skipping",
                        img_id,
                        account_name,
                    )
                    continue

                if not supports_images:
                    parts.append(
                        {
                            "type": "text",
                            "text": f"[Attached image: {img_id} — {os.path.basename(img_path)}]",
                        }
                    )
                    any_image_marked = True
                else:
                    with open(img_path, "rb") as file_handle:
                        raw = file_handle.read()
                    parts.append(
                        {
                            "type": "image",
                            "source": {
                                "data": base64.b64encode(raw).decode("ascii"),
                                "mime_type": self.guess_mime_from_path(img_path),
                            },
                        }
                    )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to resolve image_id=%s for account=%s: %s",
                    img_id,
                    account_name,
                    ex,
                )

        if any_image_marked:
            parts.append(
                {
                    "type": "text",
                    "text": (
                        "Your model cannot see images. To analyze images: create a tasklist via "
                        "tasklists_manage (action='put') with a task that includes the image UUIDs "
                        "above in meta.image_ids as a list of strings. Then run it with "
                        "tasklists_run (worker_agent='colin'). Use the worker's output to answer the user."
                    ),
                }
            )

        for file_id in (file_ids or []):
            try:
                file_path = self.find_file(images_dir, account_name, file_id)
                if file_path is None:
                    logging.warning(
                        "PromptBuilder: file_id=%s not found for account=%s; skipping",
                        file_id,
                        account_name,
                    )
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as file_handle:
                        text = file_handle.read()
                except UnicodeDecodeError:
                    text = f"[Binary file: {os.path.basename(file_path)}]"
                parts.append(
                    {
                        "type": "text",
                        "text": f"[File: {os.path.basename(file_path)}]\n{text}",
                    }
                )
            except Exception as ex:
                logging.warning(
                    "PromptBuilder: failed to resolve file_id=%s for account=%s: %s",
                    file_id,
                    account_name,
                    ex,
                )

        return parts

    def build_images_dir(self) -> str:
        return os.path.join(
            self.config.get("storage_root_path", "/home/junwin/lucy_storage"),
            self.config.get("storage_namespace", "data"),
            "images",
        )

    @staticmethod
    def find_image_file(images_dir: str, account_name: str, img_id: str) -> Optional[str]:
        if os.path.isabs(img_id) and os.path.isfile(img_id):
            return img_id
        matches = glob.glob(os.path.join(images_dir, account_name, f"{img_id}.*"))
        image_files = [path for path in matches if not path.endswith(".json")]
        return image_files[0] if image_files else None

    @classmethod
    def find_file(cls, images_dir: str, account_name: str, file_id: str) -> Optional[str]:
        if os.path.isabs(file_id) and os.path.isfile(file_id):
            return file_id
        return cls.find_image_file(images_dir, account_name, file_id)

    @staticmethod
    def guess_mime_from_path(path: str) -> str:
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
