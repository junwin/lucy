# /home/junwin/src/repos/lucy/src/handlers/handler_registry.py

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from src.handlers.handler_v2 import HandlerV2


class HandlerRegistry:
    def __init__(self) -> None:
        self._by_name: Dict[str, Type[HandlerV2]] = {}
        self._result_schemas: Dict[str, Dict[str, Any]] = {}

    def register(self, handler_cls: Type[HandlerV2]) -> None:
        name = handler_cls.name()
        if not name:
            raise ValueError("HandlerV2.name() must be non-empty")
        if name in self._by_name:
            raise ValueError(f"Duplicate handler name registered: {name}")

        self._by_name[name] = handler_cls

        # Cache schema (if any) at registration time so callers can inspect
        # capabilities without importing handler modules later.
        try:
            sch = handler_cls.result_schema()
            if sch is not None:
                self._result_schemas[name] = sch
        except Exception:
            # schema is optional; don't block startup
            pass

    def create(self, name: str, *, config: Any) -> HandlerV2:
        cls = self._by_name.get(name)
        if cls is None:
            raise KeyError(f"Unknown handler: {name}")
        # For now, assume all V2 handlers take config in __init__
        return cls(config)  # type: ignore[call-arg]

    def tools(self) -> List[Dict[str, Any]]:
        # tool_def is a classmethod (per HandlerV2 contract)
        return [cls.tool_def() for cls in self._by_name.values()]

    def tool_names(self) -> List[str]:
        return sorted(self._by_name.keys())

    def result_schema(self, name: str) -> Optional[Dict[str, Any]]:
        if name in self._result_schemas:
            return self._result_schemas[name]
        cls = self._by_name.get(name)
        if cls is None:
            return None
        return cls.result_schema()

    def all_result_schemas(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._result_schemas)
