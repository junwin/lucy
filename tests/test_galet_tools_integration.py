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

from src.handlers.command_execution_handler2 import CommandExecutionHandler2
from src.handlers.file_load_handler2 import FileLoadHandler2
from src.handlers.file_save_handler import FileSaveHandler2
from src.handlers.generate_image_handler import GenerateImageHandler
from src.handlers.generate_svg_handler import GenerateSvgHandler
from src.handlers.handler_registry import HandlerRegistry
from src.handlers.handler_v2 import HandlerV2


def test_lucy_compatibility_imports_use_canonical_galet_contract() -> None:
    assert HandlerRegistry is GaletHandlerRegistry
    assert HandlerV2 is GaletHandlerV2


def test_generic_handlers_are_thin_galet_adapters() -> None:
    assert issubclass(FileLoadHandler2, GaletFileLoadHandler2)
    assert issubclass(FileSaveHandler2, GaletFileSaveHandler2)
    assert issubclass(
        CommandExecutionHandler2,
        GaletCommandExecutionHandler2,
    )
    assert issubclass(GenerateSvgHandler, GaletGenerateSvgHandler)
    assert issubclass(GenerateImageHandler, GaletGenerateImageHandler)


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
    assert registry.has_tool("context_handler")
