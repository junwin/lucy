from src.tasklists.task_states import TASK_STATE_COMPLETED
from src.workflows.executor import (
    FakeWorkflowExecutor,
    TaskListWorkflowExecutor,
    classify_semantic_outcome,
)
from src.workflows.loader import WorkflowLoader
from src.workflows.result import WorkflowResult
from src.workflows.runner import WorkflowRunner


FLOW = """
name: issue-resolution
type: sequence
children:
  - id: clarity
    name: Requirement clarity
    type: condition
    agent: lucy
    context: lucyproject
    on:
      success: design
      failed: exit
      blocked: exit
  - id: design
    name: Create design
    type: tasklist
    max_attempts: 2
  - id: review
    name: Review design
    type: condition
    max_attempts: 2
    on:
      success: complete
      failed: design
      blocked: exit
"""


def result(outcome, text="", tokens=0, iterations=0):
    return WorkflowResult(
        execution_state="completed",
        outcome=outcome,
        text=text,
        metrics={"total_tokens": tokens, "iterations": iterations},
    )


def test_runner_executes_clarity_design_review_and_accumulates_metrics():
    root = WorkflowLoader().load_text(FLOW)
    executor = FakeWorkflowExecutor(
        {
            "clarity": result("success", tokens=10, iterations=1),
            "design": result("success", "design v1", tokens=20, iterations=2),
            "review": result("success", "approved", tokens=5, iterations=1),
        }
    )

    run = WorkflowRunner(executor).run(root)

    assert run.outcome == "success"
    assert executor.calls == ["clarity", "design", "review"]
    assert run.metrics["workflow_total_tokens"] == 35
    assert run.metrics["workflow_total_iterations"] == 4
    assert root.children[0].agent_name == "lucy"
    assert root.children[0].context_name == "lucyproject"


def test_blocked_clarity_exits_without_running_design():
    root = WorkflowLoader().load_text(FLOW)
    executor = FakeWorkflowExecutor({"clarity": result("blocked", "Need repository access")})

    run = WorkflowRunner(executor).run(root)

    assert run.outcome == "blocked"
    assert executor.calls == ["clarity"]


def test_failed_review_loops_to_design_with_feedback_and_is_bounded():
    root = WorkflowLoader().load_text(FLOW)
    executor = FakeWorkflowExecutor(
        {
            "clarity": result("success"),
            "design": [result("success", "design v1"), result("success", "design v2")],
            "review": [result("failed", "Add an explicit rollback step"), result("success", "approved")],
        }
    )

    run = WorkflowRunner(executor).run(root)

    assert run.outcome == "success"
    assert executor.calls == ["clarity", "design", "review", "design", "review"]
    assert executor.feedback_seen["design"] == ["Add an explicit rollback step"]
    assert root.children[1].attempts == 2
    assert root.children[2].attempts == 2


def test_retry_node_retries_one_child_up_to_bound():
    root = WorkflowLoader().load_text(
        """
name: retry-demo
type: sequence
children:
  - id: retry-review
    name: Retry review
    type: retry
    max_attempts: 2
    children:
      - id: review
        name: Review
        type: condition
"""
    )
    executor = FakeWorkflowExecutor(
        {"review": [result("failed", "try again"), result("success", "ok")]}
    )

    run = WorkflowRunner(executor).run(root)

    assert run.outcome == "success"
    assert executor.calls == ["review", "review"]


def test_execution_completion_is_not_automatically_semantic_success():
    assert classify_semantic_outcome("Design produced", "completed") == "inconclusive"
    assert (
        classify_semantic_outcome(
            '{"outcome":"success","result":"Design produced"}', "completed"
        )
        == "success"
    )
    assert classify_semantic_outcome("I could not access the repository", "completed") == "blocked"


class FakeAgent:
    name = "lucy"


class FakeStore:
    def __init__(self):
        self.tasklists = {}
        self.records = {}

    def save_tasklist(self, account_name, tasklist_key, tasklist):
        self.tasklists[(account_name, tasklist_key)] = tasklist

    def get_tasklist(self, account_name, tasklist_key):
        return self.tasklists.get((account_name, tasklist_key))

    def get_task_result(self, account_name, tasklist_key, task_id):
        return self.records.get((account_name, tasklist_key, task_id))


class FakeAutomationProcessor:
    def __init__(self, store):
        self.store = store
        self.calls = []

    def execute_tasklist(self, **kwargs):
        self.calls.append(kwargs)
        key = (kwargs["account_name"], kwargs["tasklist_id"])
        tasklist = self.store.tasklists[key]
        task = tasklist.tasks[0]
        task.state = TASK_STATE_COMPLETED
        self.store.records[(key[0], key[1], task.id)] = {
            "state": "completed",
            "result": {
                "output": '{"outcome":"blocked","result":"Repository is not available"}'
            },
            "metrics": {"total_tokens": 123, "iterations": 4},
        }
        self.store.save_tasklist(key[0], key[1], tasklist)
        return "[AutomationProcessor] state=Completed"


def test_tasklist_adapter_uses_existing_execution_path_and_reads_metrics():
    store = FakeStore()
    automation = FakeAutomationProcessor(store)
    node = WorkflowLoader().load_text(
        """
name: clarity
id: clarity
type: condition
agent: lucy
context: lucyproject
instructions: Assess requirement clarity and return structured JSON.
"""
    )
    executor = TaskListWorkflowExecutor(
        automation_processor=automation,
        storage=store,
        account_name="junwin",
        primary_agent=FakeAgent(),
        account={"accountId": "junwin"},
    )

    run = executor.execute(node)

    assert run.execution_state == "completed"
    assert run.outcome == "blocked"
    assert run.metrics == {"total_tokens": 123, "iterations": 4}
    assert automation.calls[0]["worker_agent"] == "lucy"
    assert automation.calls[0]["context_name"] == "lucyproject"
    assert len(store.tasklists) == 1
