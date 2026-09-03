from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .task import Task
from .task_list import TaskList


class TasklistManager(ABC):
    @abstractmethod
    def list(self, account_name: str) -> List[str]:
        pass

    @abstractmethod
    def get(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        pass

    @abstractmethod
    def save(self, account_name: str, tasklist_key: str, tasklist: TaskList) -> None:
        pass

    @abstractmethod
    def delete(self, account_name: str, tasklist_key: str) -> None:
        pass

    @abstractmethod
    def create(
        self,
        tasklist_key: str,
        name: str,
        description: str,
        *,
        meta: Optional[Dict[str, Any]] = None,
        general_instructions: str = "",
    ) -> TaskList:
        pass

    @abstractmethod
    def create_from_goal(
        self,
        tasklist_key: str,
        goal: str,
        files: Optional[List[str]] = None,
        worker_agent: Optional[str] = None,
    ) -> TaskList:
        pass

    @abstractmethod
    def add_task(
        self,
        account_name: str,
        tasklist_key: str,
        task: Task,
        *,
        after_index: Optional[int] = None,
    ) -> TaskList:
        pass

    @abstractmethod
    def update_task(
        self,
        account_name: str,
        tasklist_key: str,
        task_id: str,
        **changes: Any,
    ) -> TaskList:
        pass

    @abstractmethod
    def remove_task(self, account_name: str, tasklist_key: str, task_id: str) -> TaskList:
        pass

    @abstractmethod
    def set_state(self, account_name: str, tasklist_key: str, state: str) -> TaskList:
        pass

    @abstractmethod
    def set_name(self, account_name: str, tasklist_key: str, name: str) -> TaskList:
        pass

    @abstractmethod
    def set_description(self, account_name: str, tasklist_key: str, description: str) -> TaskList:
        pass

    @abstractmethod
    def set_general_instructions(self, account_name: str, tasklist_key: str, instructions: str) -> TaskList:
        pass

    @abstractmethod
    def update_meta(self, account_name: str, tasklist_key: str, meta: Dict[str, Any]) -> TaskList:
        pass
