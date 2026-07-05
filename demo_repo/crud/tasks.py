from typing import Any, Dict, List, Optional

from db import get_db
from auth.models import UserOut

TABLE = "tasks"
VALID_STATUSES = ("todo", "in_progress", "done")


def create_task(project_id: int, title: str, assignee: UserOut, status: str = "todo") -> Dict[str, Any]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    db = get_db()
    return db.insert(
        TABLE,
        {
            "project_id": project_id,
            "title": title,
            "assignee_id": assignee.id,
            "status": status,
        },
    )


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    return db.get(TABLE, task_id)


def list_tasks_for_project(project_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    return db.find_by(TABLE, project_id=project_id)


def set_task_status(task_id: int, status: str) -> Optional[Dict[str, Any]]:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    db = get_db()
    task = db.get(TABLE, task_id)
    if task is None:
        return None
    task["status"] = status
    db.insert(TABLE, task)
    return task


def delete_task(task_id: int) -> bool:
    db = get_db()
    return db.delete(TABLE, task_id)