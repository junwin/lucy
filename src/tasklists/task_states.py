"""Shared vocabulary constants for task lists.

These are intentionally plain constants with no persistence concerns.
"""

# Task list states
TASK_LIST_STATE_CREATED = "Created"
TASK_LIST_STATE_RUNNING = "Running"
TASK_LIST_STATE_COMPLETED = "Completed"
TASK_LIST_STATE_FAILED = "Failed"

# Task states
TASK_STATE_PENDING = "Pending"
TASK_STATE_RUNNING = "Running"
TASK_STATE_COMPLETED = "Completed"
TASK_STATE_COMPLETED_WITH_ERRORS = "Completed (with errors)"
TASK_STATE_FAILED = "Failed"
TASK_STATE_BLOCKED = "Blocked"
