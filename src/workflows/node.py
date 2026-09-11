from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WorkflowNode:
    id: str
    name: str
    type: str

    instructions: str = ""
    agent_name: Optional[str] = None
    context_name: Optional[str] = None
    tasklist_id: Optional[str] = None

    state: str = "pending"
    result_text: Optional[str] = None
    outcome: Optional[str] = None

    parent: Optional["WorkflowNode"] = field(default=None, repr=False)
    children: List["WorkflowNode"] = field(default_factory=list)

    attempts: int = 0
    max_attempts: int = 1

    on: Dict[str, str] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_child(self, child: "WorkflowNode") -> None:
        child.parent = self
        self.children.append(child)

    def walk(self) -> List["WorkflowNode"]:
        nodes = [self]
        for child in self.children:
            nodes.extend(child.walk())
        return nodes
