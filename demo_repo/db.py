"""
db.py — shared in-memory "database" layer.

Deliberately the most-imported file in the repo: auth, crud, and
notifications all depend on it. rag_service does NOT depend on it.
This asymmetry is what the blast-radius demo exploits — a change here
should legitimately affect auth + crud + notifications, but never
rag_service.
"""

from typing import Any, Dict, List, Optional
import itertools

_id_counter = itertools.count(1)


class Database:
    """Tiny in-memory table store, just enough to fake persistence."""

    def __init__(self) -> None:
        self.tables: Dict[str, Dict[int, Dict[str, Any]]] = {
            "users": {},
            "projects": {},
            "tasks": {},
            "comments": {},
        }

    def insert(self, table: str, record: Dict[str, Any]) -> Dict[str, Any]:
        record_id = next(_id_counter)
        record = {"id": record_id, **record}
        self.tables[table][record_id] = record
        return record

    def get_by_id(self, table: str, record_id: int) -> Optional[Dict[str, Any]]:
        return self.tables[table].get(record_id)

    def list(self, table: str) -> List[Dict[str, Any]]:
        return list(self.tables[table].values())

    def delete(self, table: str, record_id: int) -> bool:
        return self.tables[table].pop(record_id, None) is not None

    def find_by(self, table: str, **filters: Any) -> List[Dict[str, Any]]:
        return [
            row
            for row in self.tables[table].values()
            if all(row.get(k) == v for k, v in filters.items())
        ]


_db = Database()


def get_db() -> Database:
    """FastAPI-style dependency: yield the shared db instance."""
    return _db
