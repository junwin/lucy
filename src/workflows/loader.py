from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from .node import WorkflowNode


SUPPORTED_NODE_TYPES = frozenset({"sequence", "condition", "tasklist", "retry", "exit"})


class WorkflowLoader:
    """Load a YAML workflow definition into a linked WorkflowNode tree."""

    def load_file(self, path: str | Path) -> WorkflowNode:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return self.load_dict(data)

    def load_text(self, text: str) -> WorkflowNode:
        return self.load_dict(yaml.safe_load(text))

    def load_dict(self, data: Dict[str, Any]) -> WorkflowNode:
        if not isinstance(data, dict):
            raise ValueError("Workflow YAML root must be a mapping")

        root = self._build_node(data, default_id="workflow")
        self._validate_unique_ids(root.walk())
        self._validate_targets(root)
        return root

    def _build_node(self, data: Dict[str, Any], *, default_id: str | None = None) -> WorkflowNode:
        if not isinstance(data, dict):
            raise ValueError("Each workflow node must be a mapping")

        node_type = str(data.get("type") or "").strip()
        if node_type not in SUPPORTED_NODE_TYPES:
            raise ValueError(f"Unsupported workflow node type: {node_type or '(missing)'}")

        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Workflow node name is required")

        node_id = str(data.get("id") or default_id or "").strip()
        if not node_id:
            raise ValueError(f"Workflow node id is required for '{name}'")

        max_attempts = int(data.get("max_attempts", 1))
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1 for node '{node_id}'")

        branch_map = data.get("on") or {}
        if not isinstance(branch_map, dict):
            raise ValueError(f"on must be a mapping for node '{node_id}'")

        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata must be a mapping for node '{node_id}'")

        node = WorkflowNode(
            id=node_id,
            name=name,
            type=node_type,
            instructions=str(data.get("instructions") or ""),
            agent_name=data.get("agent"),
            context_name=data.get("context"),
            tasklist_id=data.get("tasklist"),
            max_attempts=max_attempts,
            on={str(key): str(value) for key, value in branch_map.items()},
            metadata=dict(metadata),
        )

        children = data.get("children") or []
        if not isinstance(children, list):
            raise ValueError(f"children must be a list for node '{node_id}'")
        for child_data in children:
            node.add_child(self._build_node(child_data))

        return node

    @staticmethod
    def _validate_unique_ids(nodes: Iterable[WorkflowNode]) -> None:
        seen: set[str] = set()
        for node in nodes:
            if node.id in seen:
                raise ValueError(f"Duplicate workflow node id: {node.id}")
            seen.add(node.id)

    @staticmethod
    def _validate_targets(root: WorkflowNode) -> None:
        ids = {node.id for node in root.walk()}
        for node in root.walk():
            for outcome, target in node.on.items():
                if target in {"complete", "exit", "failed"}:
                    continue
                if target not in ids:
                    raise ValueError(
                        f"Node '{node.id}' maps outcome '{outcome}' to unknown target '{target}'"
                    )
