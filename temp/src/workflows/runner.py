from __future__ import annotations

from typing import Dict

from .executor import WorkflowExecutor
from .node import WorkflowNode
from .result import WorkflowResult


class WorkflowRunner:
    """Deterministic orchestration over a WorkflowNode tree.

    The executor owns semantic work. The runner owns ordering, branches,
    bounded attempts, feedback propagation, exits, and metric accumulation.
    """

    def __init__(self, executor: WorkflowExecutor, *, max_tokens: int | None = None) -> None:
        self.executor = executor
        self.max_tokens = max_tokens
        self.total_tokens = 0
        self.total_iterations = 0

    def run(self, root: WorkflowNode) -> WorkflowResult:
        self.total_tokens = 0
        self.total_iterations = 0

        if root.type == "sequence":
            result = self._run_sequence(root)
        else:
            result = self._run_node(root)

        result.metrics = {
            **result.metrics,
            "workflow_total_tokens": self.total_tokens,
            "workflow_total_iterations": self.total_iterations,
        }
        return result

    def _run_sequence(self, sequence: WorkflowNode) -> WorkflowResult:
        sequence.state = "running"
        children = sequence.children
        sibling_index: Dict[str, int] = {child.id: index for index, child in enumerate(children)}
        index = 0
        last_result = WorkflowResult(execution_state="completed", outcome="success")

        while index < len(children):
            node = children[index]
            result = self._run_node(node)
            last_result = result

            if self._budget_exceeded():
                sequence.state = "failed"
                return WorkflowResult(
                    execution_state="completed",
                    outcome="failed",
                    text="Workflow token budget exceeded",
                    metrics=result.metrics,
                    error="token_budget_exceeded",
                )

            target = node.on.get(result.outcome)
            if target:
                if target == "complete":
                    sequence.state = "completed"
                    return result
                if target in {"exit", "failed"}:
                    sequence.state = "failed" if result.outcome != "success" else "completed"
                    return result
                if target not in sibling_index:
                    sequence.state = "failed"
                    return WorkflowResult(
                        execution_state="error",
                        outcome="failed",
                        text=result.text,
                        error=(
                            f"Branch target '{target}' from '{node.id}' is not a direct child "
                            f"of sequence '{sequence.id}'"
                        ),
                    )
                target_node = children[sibling_index[target]]
                if result.text:
                    target_node.metadata["feedback"] = result.text
                index = sibling_index[target]
                continue

            if result.outcome == "success":
                index += 1
                continue

            sequence.state = "failed"
            return result

        sequence.state = "completed"
        return last_result

    def _run_node(self, node: WorkflowNode) -> WorkflowResult:
        if node.type == "sequence":
            return self._run_sequence(node)
        if node.type == "exit":
            node.state = "completed"
            node.outcome = str(node.metadata.get("outcome") or "failed")
            return WorkflowResult(
                execution_state="completed",
                outcome=node.outcome,
                text=node.instructions,
            )
        if node.type == "retry":
            return self._run_retry(node)
        if node.type not in {"condition", "tasklist"}:
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                error=f"Unsupported executable node type: {node.type}",
            )
        return self._execute_leaf(node, attempt_limit=node.max_attempts)

    def _run_retry(self, node: WorkflowNode) -> WorkflowResult:
        if len(node.children) != 1:
            return WorkflowResult(
                execution_state="error",
                outcome="failed",
                error=f"Retry node '{node.id}' must contain exactly one child",
            )

        node.state = "running"
        child = node.children[0]
        last_result = WorkflowResult(execution_state="completed", outcome="inconclusive")
        for _ in range(node.max_attempts):
            last_result = self._execute_leaf(child, attempt_limit=node.max_attempts)
            if last_result.outcome == "success":
                node.state = "completed"
                node.outcome = "success"
                node.result_text = last_result.text
                return last_result
            if last_result.outcome == "blocked":
                break
            if last_result.text:
                child.metadata["feedback"] = last_result.text

        node.state = "failed"
        node.outcome = last_result.outcome
        node.result_text = last_result.text
        return last_result

    def _execute_leaf(self, node: WorkflowNode, *, attempt_limit: int) -> WorkflowResult:
        if node.attempts >= attempt_limit:
            node.state = "failed"
            node.outcome = "failed"
            return WorkflowResult(
                execution_state="completed",
                outcome="failed",
                text=node.result_text or "",
                error=f"Node '{node.id}' exceeded max_attempts={attempt_limit}",
            )

        node.attempts += 1
        node.state = "running"
        result = self.executor.execute(node)

        node.result_text = result.text
        node.outcome = result.outcome
        node.metrics = dict(result.metrics or {})
        node.state = "completed" if result.execution_state == "completed" else "failed"

        self.total_tokens += int(node.metrics.get("total_tokens") or 0)
        self.total_iterations += int(node.metrics.get("iterations") or 0)
        return result

    def _budget_exceeded(self) -> bool:
        return self.max_tokens is not None and self.total_tokens > self.max_tokens
