from pathlib import Path
from src.context.context import Context
from src.node_manager import NodeManager
from src.hierarchical_node import HierarchicalNode
import yaml


def create_root_step(ctx: Context, nm: NodeManager, name: str, description: str = "") -> HierarchicalNode:
    """Create the first node for a conversation and point the context at it."""
    root = HierarchicalNode(
        name=name,
        conversation_id=ctx.conversation_id,
        description=description,
        state="in_progress",
    )
    nm.add_node(root)
    ctx.current_node_id = root.id
    return root


def create_next_step(ctx: Context, nm: NodeManager, name: str, description: str = "") -> HierarchicalNode:
    """Create the next linear step under the current node and move the context to it."""
    parent = nm.get_node(ctx.current_node_id)
    parent_id = parent.id if parent else ""
    step = HierarchicalNode(
        name=name,
        conversation_id=ctx.conversation_id,
        description=description,
        parent_id=parent_id,
        state="in_progress",
    )
    nm.add_node(step)
    if parent:
        parent.add_child(step.id)
        nm.update_node(parent.id, parent)
    ctx.current_node_id = step.id
    return step


def save_state(ctx: Context, nm: NodeManager, base_dir: Path) -> None:
    """Persist context and all nodes for this conversation."""
    base_dir.mkdir(parents=True, exist_ok=True)

    # Save context as YAML
    ctx_path = base_dir / f"context_{ctx.conversation_id}.yaml"
    ctx_path.write_text(yaml.dump(ctx.to_dict(), default_flow_style=False))

    # Save nodes as JSON
    nodes_path = base_dir / f"nodes_{ctx.conversation_id}.json"
    nm.save_for_conversation(ctx.conversation_id, nodes_path)


def load_state(conversation_id: str, base_dir: Path) -> (Context, NodeManager):
    """Load context and nodes for a conversation. If missing, this will raise."""
    ctx_path = base_dir / f"context_{conversation_id}.yaml"
    nodes_path = base_dir / f"nodes_{conversation_id}.json"

    ctx_data = yaml.safe_load(ctx_path.read_text())
    ctx = Context.from_dict(ctx_data)
    nm = NodeManager.load_for_conversation(nodes_path)
    return ctx, nm
