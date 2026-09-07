import json

from src.workflows.executor import (
    AskWorkflowExecutor,
    FakeWorkflowExecutor,
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


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_ask_executor_writes_tasklist_calls_ask_and_reads_new_jsonl_record(tmp_path):
    calls = []

    def fake_post(url, *, json: payload, timeout):
        calls.append((url, payload, timeout))
        tasklist_id = payload["question"].split('tasklist "', 1)[1].split('"', 1)[0]
        history = tmp_path / f"{tasklist_id}.jsonl"
        history.write_text(
            json.dumps(
                {
                    "state": "completed",
                    "result": {
                        "output": '{"outcome":"blocked","result":"Repository is not available"}'
                    },
                    "metrics": {"total_tokens": 123, "iterations": 4},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return FakeResponse(200, {"response": "TaskList run requested", "conversation_id": "c1"})

    node = WorkflowLoader().load_text(
        """
name: clarity
id: clarity
type: condition
agent: peace
context: lucyproject
instructions: Assess requirement clarity and return structured JSON.
"""
    )
    executor = AskWorkflowExecutor(
        account_name="junwin",
        tasklist_dir=tmp_path,
        post=fake_post,
    )

    run = executor.execute(node)

    assert run.execution_state == "completed"
    assert run.outcome == "blocked"
    assert run.metrics["total_tokens"] == 123
    assert run.metrics["iterations"] == 4
    assert len(list(tmp_path.glob("workflow-clarity-*.json"))) == 1
    assert calls[0][1]["agentName"] == "peace"
    assert calls[0][1]["accountName"] == "junwin"
    assert calls[0][1]["contextName"] == "lucyproject"
    assert 'worker_agent "peace"' in calls[0][1]["question"]


def test_ask_executor_reports_http_error_before_reading_history(tmp_path):
    def fake_post(url, *, json, timeout):
        return FakeResponse(500, {"error": "Tool execution failed: tasklist not found"})

    node = WorkflowLoader().load_text(
        """
name: clarity
id: clarity
type: condition
agent: peace
instructions: Assess requirement clarity.
"""
    )
    executor = AskWorkflowExecutor(
        account_name="junwin",
        tasklist_dir=tmp_path,
        post=fake_post,
    )

    run = executor.execute(node)

    assert run.execution_state == "error"
    assert run.outcome == "failed"
    assert "HTTP 500" in run.error
    assert "tasklist not found" in run.error


def test_ask_executor_requires_new_jsonl_record_even_when_ask_returns_200(tmp_path):
    existing = tmp_path / "xyz.jsonl"
    existing.write_text(
        json.dumps({"state": "completed", "result": {"output": '{"outcome":"success"}'}}) + "\n",
        encoding="utf-8",
    )

    def fake_post(url, *, json, timeout):
        return FakeResponse(200, {"response": "I tried to run it", "conversation_id": "c1"})

    node = WorkflowLoader().load_text(
        """
name: existing
id: existing
type: tasklist
tasklist: xyz
agent: peace
"""
    )
    executor = AskWorkflowExecutor(
        account_name="junwin",
        tasklist_dir=tmp_path,
        post=fake_post,
    )

    run = executor.execute(node)

    assert run.execution_state == "error"
    assert run.outcome == "failed"
    assert run.text == "I tried to run it"
    assert "produced no new execution records" in run.error
