import json as jsonlib

from src.workflows.executor import AskWorkflowExecutor, FakeWorkflowExecutor
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

CLARITY = """
name: clarity
id: clarity
type: condition
agent: peace
context: lucyproject
instructions: Assess requirement clarity.
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
            "design": [result("success", "design v1", tokens=20, iterations=2)],
            "review": [result("success", "approved", tokens=5, iterations=1)],
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


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


def test_ask_executor_reads_api_key_from_config_local_json(tmp_path):
    config_path = tmp_path / "config.local.json"
    config_path.write_text(jsonlib.dumps({"api_key": "sekret"}), encoding="utf-8")

    executor = AskWorkflowExecutor(
        account_name="junwin",
        config_path=config_path,
        post=lambda *args, **kwargs: None,
    )

    assert executor.api_key == "sekret"


def test_ask_executor_sends_node_instructions_as_the_question():
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append((url, json, headers, timeout))
        return FakeResponse(200, {"response": "Design produced"})

    node = WorkflowLoader().load_text(CLARITY)
    executor = AskWorkflowExecutor(account_name="junwin", api_key="sekret", post=fake_post)

    run = executor.execute(node)

    assert len(calls) == 1
    url, payload, headers, timeout = calls[0]
    assert url == executor.ask_url
    assert headers == {"X-API-Key": "sekret"}
    assert payload["question"] == "Assess requirement clarity."
    assert payload["agentName"] == "peace"
    assert payload["accountName"] == "junwin"
    assert payload["contextName"] == "lucyproject"
    assert run.execution_state == "completed"
    assert run.text == "Design produced"
    assert run.outcome == "success"
    assert run.metrics == {}


def test_ask_executor_does_not_interpret_response_text():
    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(200, {"response": '{"outcome":"failed","result":"ok"}'})

    node = WorkflowLoader().load_text(CLARITY)
    executor = AskWorkflowExecutor(account_name="junwin", api_key="sekret", post=fake_post)

    run = executor.execute(node)

    assert run.execution_state == "completed"
    assert run.outcome == "success"


def test_ask_executor_reports_http_error():
    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(500, {"error": "boom"})

    node = WorkflowLoader().load_text(CLARITY)
    executor = AskWorkflowExecutor(account_name="junwin", api_key="sekret", post=fake_post)

    run = executor.execute(node)

    assert run.execution_state == "error"
    assert run.outcome == "failed"
    assert "HTTP 500" in run.error
    assert "boom" in run.error


def test_ask_executor_reports_ask_error_body():
    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(200, {"error": "boom"})

    node = WorkflowLoader().load_text(CLARITY)
    executor = AskWorkflowExecutor(account_name="junwin", api_key="sekret", post=fake_post)

    run = executor.execute(node)

    assert run.execution_state == "error"
    assert run.outcome == "failed"
    assert "boom" in run.error


def test_ask_executor_reports_transport_failure():
    def fake_post(url, *, json, headers, timeout):
        raise ConnectionError("connection refused")

    node = WorkflowLoader().load_text(CLARITY)
    executor = AskWorkflowExecutor(account_name="junwin", api_key="sekret", post=fake_post)

    run = executor.execute(node)

    assert run.execution_state == "error"
    assert run.outcome == "failed"
    assert "connection refused" in run.error


def test_ask_executor_writes_no_files(tmp_path):
    def fake_post(url, *, json, headers, timeout):
        return FakeResponse(200, {"response": "Design produced"})

    node = WorkflowLoader().load_text(CLARITY)
    executor = AskWorkflowExecutor(account_name="junwin", api_key="sekret", post=fake_post)

    run = executor.execute(node)

    assert run.execution_state == "completed"
    assert list(tmp_path.iterdir()) == []
