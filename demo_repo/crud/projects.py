from typing import Any, Dict, List, Optional

from db import get_db
from auth.models import UserOut

TABLE = "projects"


def create_project(name: str, description: str, owner: UserOut) -> Dict[str, Any]:
    db = get_db()
    return db.insert(
        TABLE,
        {
            "name": name,
            "description": description,
            "owner_id": owner.id,
        },
    )


def get_project(project_id: int) -> Optional[Dict[str, Any]]:
    db = get_db()
    return db.get_by_id(TABLE, project_id)


def list_projects_for_owner(owner: UserOut) -> List[Dict[str, Any]]:
    db = get_db()
    return db.find_by(TABLE, owner_id=owner.id)


def update_project(project_id: int, owner: UserOut, **fields: Any) -> Optional[Dict[str, Any]]:
    db = get_db()
    project = db.get_by_id(TABLE, project_id)
    if project is None or project["owner_id"] != owner.id:
        return None
    db.tables[TABLE][project_id].update(fields)
    return db.tables[TABLE][project_id]


def delete_project(project_id: int, owner: UserOut) -> bool:
    db = get_db()
    project = db.get_by_id(TABLE, project_id)
    if project is None or project["owner_id"] != owner.id:
        return False
    return db.delete(TABLE, project_id)