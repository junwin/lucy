import pytest

from src.workflows.loader import WorkflowLoader


WORKFLOW_YAML = """
name: demo
id: root
type: sequence
children:
  - id: clarity
    name: Requirement clarity
    type: condition
    agent: lucy
    context: lucyproject
    on:
      success: design
      blocked: exit
  - id: design
    name: Design
    type: tasklist
    max_attempts: 2
"""


def test_loader_builds_linked_tree_and_preserves_execution_fields():
    root = WorkflowLoader().load_text(WORKFLOW_YAML)

    assert root.id == "root"
    assert root.type == "sequence"
    assert [child.id for child in root.children] == ["clarity", "design"]

    clarity = root.children[0]
    assert clarity.parent is root
    assert clarity.agent_name == "lucy"
    assert clarity.context_name == "lucyproject"
    assert clarity.on == {"success": "design", "blocked": "exit"}
    assert root.children[1].max_attempts == 2


def test_loader_rejects_unknown_branch_target():
    bad_yaml = """
name: demo
type: sequence
children:
  - id: clarity
    name: Requirement clarity
    type: condition
    on:
      success: missing-node
"""

    with pytest.raises(ValueError, match="unknown target"):
        WorkflowLoader().load_text(bad_yaml)


def test_loader_rejects_duplicate_ids():
    bad_yaml = """
name: demo
type: sequence
children:
  - id: same
    name: One
    type: condition
  - id: same
    name: Two
    type: tasklist
"""

    with pytest.raises(ValueError, match="Duplicate workflow node id"):
        WorkflowLoader().load_text(bad_yaml)
