from src.execution_identity import ExecutionIdentity


def test_root_ids_are_server_owned_even_for_repeated_or_invalid_message_ids():
    first = ExecutionIdentity.root(message_id="bogus")
    second = ExecutionIdentity.root(message_id="bogus")

    assert first.trace_id == first.run_id
    assert second.trace_id == second.run_id
    assert first.run_id != second.run_id
    assert first.message_id == second.message_id == "bogus"
    assert first.parent_run_id is None


def test_child_and_retry_keep_trace_but_get_distinct_runs():
    root = ExecutionIdentity.root(message_id="client-message")
    child = root.child()
    retry = root.child()
    grandchild = child.child()

    assert len({root.run_id, child.run_id, retry.run_id, grandchild.run_id}) == 4
    assert child.trace_id == retry.trace_id == grandchild.trace_id == root.trace_id
    assert child.parent_run_id == retry.parent_run_id == root.run_id
    assert grandchild.parent_run_id == child.run_id
    assert grandchild.message_id == "client-message"
