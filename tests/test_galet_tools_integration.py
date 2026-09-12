from __future__ import annotations

from galet_tools import HandlerRegistry as GaletHandlerRegistry
from galet_tools.framework import HandlerV2 as GaletHandlerV2

from src.handlers.handler_registry import HandlerRegistry
from src.handlers.handler_v2 import HandlerV2


def test_lucy_compatibility_imports_use_canonical_galet_contract() -> None:
    assert HandlerRegistry is GaletHandlerRegistry
    assert HandlerV2 is GaletHandlerV2


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
