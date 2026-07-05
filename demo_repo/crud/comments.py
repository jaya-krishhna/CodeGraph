"""
crud/comments.py — CRUD operations for comments left on tasks.

Imports:
  - db (shared persistence layer)
  - auth.models (UserOut, to attribute authorship)
"""

from typing import Any, Dict, List, Optional

from db import get_db
from auth.models import UserOut

TABLE = "comments"
MAX_BODY_LENGTH = 2000


def create_comment(task_id: int, body: str, author: UserOut) -> Dict[str, Any]:
    if not body.strip():
        raise ValueError("comment body cannot be empty")
    if len(body) > MAX_BODY_LENGTH:
        raise ValueError("comment body too long")

    db = get_db()
    return db.insert(
        TABLE,
        {
            "task_id": task_id,
            "body": body,
            "author_id": author.id,
        },
    )


def get_comment(comment_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    return db.get(TABLE, comment_id)


def list_comments_for_task(task_id: int) -> List[Dict[str, Any]]:
    db = get_db()
    return db.find_by(TABLE, task_id=task_id)


def delete_comment(comment_id: int, requester: UserOut) -> bool:
    db = get_db()
    comment = db.get(TABLE, comment_id)
    if comment is None or comment["author_id"] != requester.id:
        return False
    return db.delete(TABLE, comment_id)
