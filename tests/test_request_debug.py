"""Diagnostic snapshots retain comparison data without logging image payloads."""

import ast
import importlib.util
import json
from pathlib import Path
import unittest
import logging
from types import SimpleNamespace
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "request_debug_under_test", Path(__file__).parents[1] / "src" / "request_debug.py"
)
debug = importlib.util.module_from_spec(spec)
spec.loader.exec_module(debug)


class TestRequestDebug(unittest.TestCase):
    def config(self, enabled):
        return Mock(get=Mock(return_value=enabled))

    def snapshot(self, **details):
        with patch.object(debug.logger, "info") as info:
            debug.log_request_debug(self.config(True), "prepared_prompt",
                                    correlation_id="turn-1", **details)
        return json.loads(info.call_args.args[1])

    def test_disabled_does_not_inspect_or_log_prompt(self):
        for setting in (False, None, "true", 1):
            with patch.object(debug, "_snapshot") as snapshot, patch.object(debug.logger, "info") as info:
                debug.log_request_debug(self.config(setting), "prepared_prompt", messages=object())
                snapshot.assert_not_called()
                info.assert_not_called()

    def test_preserves_agent_attachment_and_prompt_comparison_fields(self):
        messages = [{"role": "system", "content": "Use video_generate"},
                    {"role": "user", "content": [{"type": "text", "text": "Animate this\nimage-id-1"}]}]
        value = self.snapshot(agent_name="lumia", supports_images=False,
                              context_name="image_tool", image_ids=["image-id-1"],
                              messages=messages, tools=[{"name": "video_generate"}])
        self.assertEqual(value["correlation_id"], "turn-1")
        self.assertEqual(value["messages"], messages)
        self.assertEqual(value["image_ids"], ["image-id-1"])
        self.assertEqual(value["tools"], [{"name": "video_generate"}])

    def test_omits_provider_neutral_and_provider_specific_inline_images(self):
        value = self.snapshot(messages=[
            {"type": "image", "source": {"data": "secret-base64", "mime_type": "image/jpeg"}},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,secret-base64"}},
            {"type": "input_image", "image_url": "data:image/jpeg;base64,secret-base64"},
        ], image_bytes=b"secret-bytes")
        text = json.dumps(value)
        self.assertNotIn("secret-base64", text)
        self.assertNotIn("secret-bytes", text)
        self.assertIn("image/jpeg", text)
        self.assertEqual(value["messages"][0]["source"]["data"]["length"], 13)

    def test_long_text_is_bounded_and_differences_remain_detectable(self):
        first = self.snapshot(messages=["x" * 21000])["messages"][0]
        second = self.snapshot(messages=["x" * 20999 + "y"])["messages"][0]
        self.assertEqual(len(first["preview"]), 20000)
        self.assertEqual(first["length"], 21000)
        self.assertTrue(first["truncated"])
        self.assertNotEqual(first["sha256"], second["sha256"])

    def test_logging_failure_does_not_break_execution(self):
        with patch.object(debug.logger, "info", side_effect=RuntimeError("bad sink")), patch.object(debug.logger, "warning") as warning:
            debug.log_request_debug(self.config(True), "prepared_prompt", messages=["hello"])
            warning.assert_called_once()


    def test_actual_prompt_preparation_accepts_agent_without_optional_fields(self):
        # Execute the real preparation method with lightweight collaborators,
        # without importing the application's optional runtime dependencies.
        source = (Path(__file__).parents[1] / "src" / "message_processors"
                  / "function_calling_processor.py").read_text()
        tree = ast.parse(source)
        method = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_prepare_prompt_and_tools")
        module = ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            method,
        ], type_ignores=[])
        namespace = {
            "logging": logging,
            "log_request_debug": debug.log_request_debug,
            "ProviderRegistry": SimpleNamespace(resolve_name=lambda *args: "test"),
            "_log_token_breakdown": lambda *args: {},
            "_PromptSetupResult": SimpleNamespace,
        }
        exec(compile(ast.fix_missing_locations(module), source, "exec"), namespace)
        for enabled in (False, True):
            config = Mock()
            config.get.side_effect = lambda key, default=None: (
                enabled if key == "request_routing_debug" else default
            )
            processor = SimpleNamespace(
                config=config, registry=None,
                llm_adapter=SimpleNamespace(supports_image_processing=lambda *args: False),
                _get_environment_system_messages=lambda: [],
                prompt_builder=SimpleNamespace(build_prompt=lambda **kwargs: [
                    {"role": "user", "content": "Animate this image"}
                ]),
                _resolve_tool_defs_pipeline=lambda **kwargs: [],
            )
            ctx = SimpleNamespace(model="test", provider=None, conversation_id="chat-1",
                                  agent_name="lumia", account_id="john",
                                  context_type="hybrid", context_name="image_tool")
            with patch.object(debug.logger, "info") as info:
                result = namespace["_prepare_prompt_and_tools"](
                    processor, ctx=ctx, primary_agent=SimpleNamespace(),
                    message="Animate this image", image_ids=["image-1"], file_ids=None,
                )
            self.assertEqual(result.prompt_messages[0]["content"], "Animate this image")
            if enabled:
                record = json.loads(info.call_args.args[1])
                self.assertIsNone(record["allowed_tools"])
                self.assertEqual(record["image_ids"], ["image-1"])
            else:
                info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
