from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .task_list import TaskList


class TasklistManager(ABC):
    @abstractmethod
    def list(self, account_name: str) -> List[str]:
        pass

    @abstractmethod
    def get(self, account_name: str, tasklist_key: str) -> Optional[TaskList]:
        pass

    @abstractmethod
    def get_task_result(
        self, account_name: str, tasklist_key: str, task_id: str
    ) -> Optional[dict]:
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
        *,
        task_id: str,
        task_name: str,
        task_instructions: str = "",
        task_state: Optional[str] = None,
        task_agent: Optional[str] = None,
        task_meta: Optional[Dict[str, Any]] = None,
        task_position: Optional[int] = None,
        task_parent_id: Optional[str] = None,
        task_files: Optional[List[str]] = None,
        after_index: Optional[int] = None,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def update_task(
        self,
        account_name: str,
        tasklist_key: str,
        task_id: str,
        *,
        validate_only: bool = False,
        **changes: Any,
    ) -> TaskList:
        pass

    @abstractmethod
    def remove_task(
        self,
        account_name: str,
        tasklist_key: str,
        task_id: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def set_state(
        self,
        account_name: str,
        tasklist_key: str,
        state: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def set_name(
        self,
        account_name: str,
        tasklist_key: str,
        name: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def set_description(
        self,
        account_name: str,
        tasklist_key: str,
        description: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def set_general_instructions(
        self,
        account_name: str,
        tasklist_key: str,
        instructions: str,
        *,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def update_meta(
        self,
        account_name: str,
        tasklist_key: str,
        meta: Dict[str, Any],
        *,
        validate_only: bool = False,
    ) -> TaskList:
        pass

    @abstractmethod
    def reset(self, tasklist: TaskList) -> TaskList:
        pass
