"""Lucy compatibility adapter for galet-tools' video_generate handler."""

from galet_tools.tools.video_generate_handler import (
    VideoGenerateHandler as GaletVideoGenerateHandler,
)

from src.handlers.galet_adapters import LucyStorageLocationResolver


class VideoGenerateHandler(GaletVideoGenerateHandler):
    """Keep Lucy's ConfigManager constructor while using Galet's implementation."""

    def __init__(self, config) -> None:
        self.config = config
        super().__init__(LucyStorageLocationResolver(config))

    def execute(self, args, *, account_name="auto", **context):
        result = super().execute(args, account_name=account_name, **context)
        if result.get("ok") and isinstance(result.get("video"), dict):
            # Preserve which still produced the video for later prompt revisions.
            result["video"]["source_image_id"] = args["image_id"]
        return result

    @classmethod
    def result_schema(cls):
        schema = super().result_schema()
        schema["properties"]["video"]["properties"]["source_image_id"] = {"type": "string"}
        return schema


__all__ = ["VideoGenerateHandler"]
