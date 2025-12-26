from pathlib import Path
from src.context.context import Context
from src.node_manager import NodeManager
from src.task_flow import create_root_step, create_next_step, save_state, load_state


def test_linear_task_flow(tmp_path: Path):
    # Initial setup
    ctx = Context(
        name="My Task",
        description="Do something in steps",
        current_node_id="",
        state="in_progress",
        conversation_id="conv1",
    )
    nm = NodeManager()

    # Create root step
    root = create_root_step(ctx, nm, name="Root", description="Root step")
    assert ctx.current_node_id == root.id

    # Add first step
    step1 = create_next_step(ctx, nm, name="Step 1", description="First step")
    assert ctx.current_node_id == step1.id
    assert step1.parent_id == root.id

    # Log an action
    ctx.add_action("do step 1", "done", "ok")

    # Persist
    save_state(ctx, nm, tmp_path)

    # Load again
    ctx2, nm2 = load_state("conv1", tmp_path)
    assert ctx2.current_node_id == ctx.current_node_id

    # Check nodes
    nodes = nm2.get_nodes_conversation_id("conv1")
    names = sorted(n.name for n in nodes)
    assert names == ["Root", "Step 1"]
