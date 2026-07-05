"""
notifications/notifier.py — sends notifications when tasks/comments change.

Imports:
  - db (to look up the target user's contact info and log the notification)

Deliberately does NOT import auth or crud directly — it receives plain
ids/strings from callers, and only touches db.py. This keeps it a
one-hop dependent of db.py for the blast-radius demo.
"""

from typing import Any, Dict, List

from db import get_db

TABLE = "notifications"


def _ensure_table(db) -> None:
    if TABLE not in db.tables:
        db.tables[TABLE] = {}


def notify_user(user_id: int, message: str, kind: str = "info") -> Dict[str, Any]:
    db = get_db()
    _ensure_table(db)
    return db.insert(
        TABLE,
        {
            "user_id": user_id,
            "message": message,
            "kind": kind,
            "read": False,
        },
    )


def notify_task_assigned(user_id: int, task_title: str) -> Dict[str, Any]:
    return notify_user(user_id, f"You were assigned: {task_title}", kind="task_assigned")


def notify_new_comment(user_id: int, task_title: str) -> Dict[str, Any]:
    return notify_user(user_id, f"New comment on: {task_title}", kind="new_comment")


def list_unread(user_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    _ensure_table(db)
    return [n for n in db.tables[TABLE].values() if n["user_id"] == user_id and not n["read"]]


def mark_read(notification_id: int) -> bool:
    db = get_db()
    _ensure_table(db)
    notification = db.tables[TABLE].get(notification_id)
    if notification is None:
        return False
    notification["read"] = True
    return True
