from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, Annotated
import json
import uuid
import copy
from pathlib import Path
from datetime import datetime

from .task import Task
from .task_states import TASK_LIST_STATE_CREATED


@dataclass
class TaskList:
    schema_version: int = 1
    state: str = TASK_LIST_STATE_CREATED
    tasks: List[Task] = field(default_factory=list)
    # Persisted runs metadata keyed by run_id. This is stored alongside the
    # tasklist dict so automation processors can create/resume runs.
    runs: Dict[str, Any] = field(default_factory=dict)

    # -----------------
    # Domain behavior
    # -----------------

    def task_list(self) -> Iterable[Task]:
        return list(self.tasks)

    def get_task(self, id: int) -> Optional[Task]:
        for t in self.tasks:
            if t.id == id:
                return t
        return None

    def next_id(self) -> int:
        if not self.tasks:
            return 1
        return max(t.id for t in self.tasks) + 1

    def add_task(self, task: Task) -> None:
        for i, existing in enumerate(self.tasks):
            if existing.id == task.id:
                self.tasks[i] = task
                return
        self.tasks.append(task)

    def update_task_state(self, id: int, new_state: str) -> None:
        t = self.get_task(id)
        if t:
            t.state = new_state

    def set_task_result(
        self,
        id: int,
        result: Dict[str, Any],
        *,
        new_state: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        t = self.get_task(id)
        if not t:
            return
        t.result = result
        if error is not None:
            t.error = error
        if new_state is not None:
            t.state = new_state

    # -----------------
    # Serialization helpers
    # -----------------

    def to_dict(self) -> Dict[str, Any]:
        """
        Return a plain dict representation of the TaskList (no storage metadata).
        """
        return {
            "schema_version": self.schema_version,
            "state": self.state,
            "tasks": [asdict(task) for task in self.tasks],
            "runs": self.runs,
        }

    def to_json(self) -> str:
        """
        Serialize TaskList → JSON string (no storage metadata).
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskList":
        """
        Construct TaskList from a dict produced by to_dict / persisted task content.
        """
        tasks = [Task(**task_dict) for task_dict in data.get("tasks", [])]
        tl = cls(
            schema_version=data.get("schema_version", 1),
            state=data.get("state", TASK_LIST_STATE_CREATED),
            tasks=tasks,
        )
        # restore runs metadata if present
        tl.runs = data.get("runs", {})
        return tl

    @classmethod
    def from_json(cls, json_str: str) -> "TaskList":
        """
        Deserialize JSON string → TaskList (expects the simple tasklist dict format).
        """
        data = json.loads(json_str)
        return cls.from_dict(data)


# -----------------
# Storage helper
# -----------------

class TaskListStorage:
    """
    Simple filesystem-backed storage helper for TaskList templates and runs.

    Storage layout (under a provided storage_root):
      tasklists/templates/<account>/<template_id>.json
      tasklists/runs/<account>/<run_id>.json

    File schema (JSON):
    {
      "schema_version": <int>,
      "metadata": {
          "template_id": <str, optional>,
          "run_id": <str, optional>,
          "created_at": <ISO8601 str>,
          "updated_at": <ISO8601 str>
      },
      "tasklist": { ... }  # output of TaskList.to_dict()
    }

    Notes:
    - Create/ensure directories as needed.
    - Methods return tuple(TaskList, metadata_dict) when loading.
    - YAML input is intentionally optional and not required by these helpers;
      callers may parse YAML and construct a TaskList before calling save_template().

    Usage examples:
      storage = TaskListStorage(Path("/var/lib/lucy/storage"))
      tpl, meta = storage.load_template("acct1", "welcome")
      run_id = storage.create_run_from_template("acct1", "welcome")
      run, run_meta = storage.load_run("acct1", run_id)
    """

    def __init__(self, storage_root: Path | str):
        self.root = Path(storage_root)
        self.templates_dir = self.root / "tasklists" / "templates"
        self.runs_dir = self.root / "tasklists" / "runs"

    # Path helpers
    def _template_path(self, account: str, template_id: str) -> Path:
        return self.templates_dir / account / f"{template_id}.json"

    def _run_path(self, account: str, run_id: str) -> Path:
        return self.runs_dir / account / f"{run_id}.json"

    def _now(self) -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    # Template operations
    def save_template(self, account: str, template_id: str, tasklist: TaskList) -> Dict[str, Any]:
        p = self._template_path(account, template_id)
        p.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "template_id": template_id,
            "created_at": self._now(),
            "updated_at": self._now(),
        }

        payload = {
            "schema_version": tasklist.schema_version,
            "metadata": metadata,
            "tasklist": tasklist.to_dict(),
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        return metadata

    def load_template(self, account: str, template_id: str) -> Tuple[TaskList, Dict[str, Any]]:
        p = self._template_path(account, template_id)
        with p.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        tasklist = TaskList.from_dict(payload.get("tasklist", {}))
        metadata = payload.get("metadata", {})
        return tasklist, metadata

    def list_templates(self, account: str) -> List[str]:
        d = self.templates_dir / account
        if not d.exists():
            return []
        return [p.stem for p in d.glob("*.json") if p.is_file()]

    # Run operations
    def save_run(self, account: str, run_id: str, tasklist: TaskList, template_id: Optional[str] = None) -> Dict[str, Any]:
        p = self._run_path(account, run_id)
        p.parent.mkdir(parents=True, exist_ok=True)

        now = self._now()
        metadata = {
            "run_id": run_id,
            "template_id": template_id,
            "created_at": now,
            "updated_at": now,
        }

        payload = {
            "schema_version": tasklist.schema_version,
            "metadata": metadata,
            "tasklist": tasklist.to_dict(),
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

        return metadata

    def load_run(self, account: str, run_id: str) -> Tuple[TaskList, Dict[str, Any]]:
        p = self._run_path(account, run_id)
        with p.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        tasklist = TaskList.from_dict(payload.get("tasklist", {}))
        metadata = payload.get("metadata", {})
        return tasklist, metadata

    def list_runs(self, account: str) -> List[str]:
        d = self.runs_dir / account
        if not d.exists():
            return []
        return [p.stem for p in d.glob("*.json") if p.is_file()]

    def create_run_from_template(self, account: str, template_id: str, run_id: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Create a new run by copying the template content. Returns (run_id, metadata).
        If run_id is None a random uuid4 hex is used.
        """
        if run_id is None:
            run_id = uuid.uuid4().hex

        template_path = self._template_path(account, template_id)
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        # Load template
        with template_path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        tasklist_dict = payload.get("tasklist", {})
        # Deep-copy to ensure run modifications don't affect template in-memory
        tasklist_for_run = TaskList.from_dict(copy.deepcopy(tasklist_dict))

        # register run metadata on the copied tasklist so callers can inspect runs
        run_meta = self.save_run(account, run_id, tasklist_for_run, template_id=template_id)
        # store run metadata on the template file as well for discoverability
        try:
            tpl_tasklist = TaskList.from_dict(payload.get("tasklist", {}))
            tpl_tasklist.runs[run_id] = run_meta
            # overwrite template with updated runs metadata
            self.save_template(account, template_id, tpl_tasklist)
        except Exception:
            # non-fatal: if we can't update template, continue — run was created
            pass

        return run_id, run_meta

    # Helper to update run on each state change (persist updated tasklist and update timestamp)
    def persist_run_update(self, account: str, run_id: str, tasklist: TaskList) -> Dict[str, Any]:
        p = self._run_path(account, run_id)
        if not p.exists():
            raise FileNotFoundError(f"Run not found: {p}")

        with p.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        metadata = payload.get("metadata", {})
        metadata["updated_at"] = self._now()

        new_payload = {
            "schema_version": tasklist.schema_version,
            "metadata": metadata,
            "tasklist": tasklist.to_dict(),
        }

        with p.open("w", encoding="utf-8") as fh:
            json.dump(new_payload, fh, indent=2)

        return metadata


# -----------------
# Automation wiring
# -----------------

class AutomationProcessor:
    """
    Lightweight helper to wire JSON payloads to TaskListStorage operations.

    Expected payload (JSON/dict):
      {
        "account": "<account>",                      # REQUIRED (B1)
        "template_id": "<template_id>",            # optional for create
        "run_id": "<run_id>",                      # optional to resume
        "action": "create" | "resume" | "create_or_resume"  # optional
      }

    Behavior:
      - "create": requires template_id; creates a new run from template
      - "resume": requires run_id; loads the run
      - "create_or_resume": if run_id provided loads run, else creates from template_id
      - If action omitted, behavior is inferred: prefer run_id (resume) otherwise create from template_id

    The processor enforces that "account" is present in the payload (B1) and
    exposes convenience methods to update task state/result which persist
    the run after each change.
    """

    def __init__(self, storage_root: Annotated[Path | str, "storage_root"]):
        self.storage = TaskListStorage(storage_root)

    def process_payload(self, payload: Annotated[str | Dict[str, Any], "json payload"]) -> Tuple[str, Dict[str, Any]]:
        """Process the provided payload and either create or load a run.

        Returns (run_id, metadata)
        """
        if isinstance(payload, str):
            data = json.loads(payload)
        else:
            data = dict(payload)

        account = data.get("account")
        if not account:
            raise ValueError("payload must include 'account'")

        action = data.get("action")
        run_id = data.get("run_id")
        template_id = data.get("template_id")

        # Infer action if not provided
        if not action:
            if run_id:
                action = "resume"
            elif template_id:
                action = "create"

        if action == "create":
            if not template_id:
                raise ValueError("create action requires 'template_id'")
            run_id = data.get("run_id")
            created_run_id, meta = self.storage.create_run_from_template(account, template_id, run_id=run_id)
            return created_run_id, meta

        if action == "resume":
            if not run_id:
                raise ValueError("resume action requires 'run_id'")
            _, meta = self.storage.load_run(account, run_id)
            return run_id, meta

        if action == "create_or_resume":
            if run_id:
                _, meta = self.storage.load_run(account, run_id)
                return run_id, meta
            if not template_id:
                raise ValueError("create_or_resume requires either 'run_id' or 'template_id'")
            created_run_id, meta = self.storage.create_run_from_template(account, template_id)
            return created_run_id, meta

        raise ValueError(f"unknown action: {action}")

    def update_task_state(self, account: str, run_id: str, task_id: int, new_state: str) -> Dict[str, Any]:
        """Load a run, update a task's state, persist the run, and return updated metadata."""
        tasklist, _ = self.storage.load_run(account, run_id)
        tasklist.update_task_state(task_id, new_state)
        meta = self.storage.persist_run_update(account, run_id, tasklist)
        return meta

    def set_task_result(self, account: str, run_id: str, task_id: int, result: Dict[str, Any], *, new_state: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        """Load a run, set a task's result (and optionally new_state/error), persist and return metadata."""
        tasklist, _ = self.storage.load_run(account, run_id)
        tasklist.set_task_result(task_id, result, new_state=new_state, error=error)
        meta = self.storage.persist_run_update(account, run_id, tasklist)
        return meta
