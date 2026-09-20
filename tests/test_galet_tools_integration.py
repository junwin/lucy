from __future__ import annotations

from galet_tools import HandlerRegistry as GaletHandlerRegistry
from galet_tools.framework import HandlerV2 as GaletHandlerV2
from galet_tools.tools.command_execution_handler2 import (
    CommandExecutionHandler2 as GaletCommandExecutionHandler2,
)
from galet_tools.tools.file_load_handler2 import (
    FileLoadHandler2 as GaletFileLoadHandler2,
)
from galet_tools.tools.file_save_handler import (
    FileSaveHandler2 as GaletFileSaveHandler2,
)
from galet_tools.tools.generate_image_handler import (
    GenerateImageHandler as GaletGenerateImageHandler,
)
from galet_tools.tools.generate_svg_handler import (
    GenerateSvgHandler as GaletGenerateSvgHandler,
)
from galet_tools.tools.patch_apply_handler import (
    PatchApplyHandler2 as GaletPatchApplyHandler2,
)

from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2
from src.handlers.generate_image_handler import GenerateImageHandler
from src.handlers.generate_svg_handler import GenerateSvgHandler
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.handler_v2 import HandlerV2
from src.handlers.patch_apply_handler import PatchApplyHandler


def test_lucy_compatibility_imports_use_canonical_galet_contract() -> None:
    assert HandlerRegistry is GaletHandlerRegistry
    assert HandlerV2 is GaletHandlerV2


def test_generic_handlers_are_thin_galet_adapters() -> None:
    assert issubclass(FileLoadHandler2, GaletFileLoadHandler2)
    assert issubclass(FileSaveHandler2, GaletFileSaveHandler2)
    assert issubclass(
        CommandExecutionHandler2,
        GaletExecuteCommand2,
    )
    assert issubclass(GenerateSvgHandler, GaletGenerateSvgHandler)
    assert issubclass(GenerateImageHandler, GaletGenerateImageHandler)
    assert issubclass(PatchApplyHandler, GaletPatchApplyHandler2)


class DictConfig:
    def __init__(self, values: dict) -> None:
        self._values = values

    def get(self, key: str, default=None):
        return self._values.get(key, default)


def test_file_adapters_round_trip_through_lucy_storage(tmp_path) -> None:
    storage_root = tmp_path / "storage-root"
    storage_root.mkdir()
    config = DictConfig(
        {
            "storage_root_path": str(storage_root),
            "storage_namespace": "account-data",
            "external_roots": {},
        }
    )

    saved = FileSaveHandler2(config).execute(
        {
            "location": "storage",
            "external_root": "",
            "path": "adapter-check.txt",
            "file_content": "owned by galet-tools",
            "overwrite": True,
        }
    )
    loaded = FileLoadHandler2(config).execute(
        {
            "location": "storage",
            "external_root": "",
            "path": "adapter-check.txt",
        }
    )

    assert saved["ok"] is True
    assert loaded["ok"] is True
    assert loaded["result"] == "owned by galet-tools"


def test_registry_bootstrap_loads_installed_handler_plugins(monkeypatch) -> None:
    from src.handlers import registry_bootstrap

    observed: list[HandlerRegistry] = []

    def discover(registry: HandlerRegistry) -> list[str]:
        observed.append(registry)
        return ["test-plugin"]

    monkeypatch.setattr(
        registry_bootstrap,
        "register_installed_handlers",
        discover,
    )

    registry = registry_bootstrap.build_registry()

    assert observed == [registry]
    assert registry.has_tool("file_load")
    assert registry.has_tool("patch_apply")
    assert registry.has_tool("context_handler")


def test_file_load_adapter_supports_ranged_reads(tmp_path) -> None:
    storage_root = tmp_path / "storage-root"
    storage_root.mkdir()
    config = DictConfig(
        {
            "storage_root_path": str(storage_root),
            "storage_namespace": "account-data",
            "external_roots": {},
        }
    )
    target_dir = storage_root / "account-data"
    target_dir.mkdir()
    (target_dir / "lines.txt").write_text(
        "one\ntwo\nthree\nfour\n",
        encoding="utf-8",
    )

    loaded = FileLoadHandler2(config).execute(
        {
            "location": "storage",
            "external_root": "",
            "path": "lines.txt",
            "start_line": 2,
            "line_count": 2,
            "include_line_numbers": True,
        }
    )

    assert loaded["ok"] is True
    assert loaded["result"] == "2: two\n3: three\n"
    assert loaded["start_line"] == 2
    assert loaded["end_line"] == 3
    assert loaded["total_lines"] == 4
    assert loaded["has_more"] is True


def test_patch_apply_adapter_uses_lucy_external_roots(tmp_path) -> None:
    target = tmp_path / "hello.txt"
    target.write_text("old\n", encoding="utf-8")
    config = DictConfig(
        {
            "storage_root_path": str(tmp_path / "storage"),
            "storage_namespace": "account-data",
            "external_roots": {"repo": str(tmp_path)},
        }
    )
    patch = (
        "--- a/hello.txt\n"
        "+++ b/hello.txt\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    result = PatchApplyHandler(config).execute(
        {
            "location": "external",
            "external_root": "repo",
            "path": "hello.txt",
            "patch_content": patch,
            "check_only": False,
        }
    )

    assert result["ok"] is True
    assert result["applied"] is True
    assert result["affected_paths"] == ["hello.txt"]
    assert target.read_text(encoding="utf-8") == "new\n"


def test_file_load_strict_schema_exposes_range_arguments() -> None:
    parameters = FileLoadHandler2.tool_def()["parameters"]

    assert set(parameters["required"]) == set(parameters["properties"])
    assert {"start_line", "line_count", "include_line_numbers"} <= set(
        parameters["properties"]
    )
