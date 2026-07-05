"""
rag_service/retriever.py — standalone document retrieval.

Deliberately isolated: no imports from db.py, auth/, crud/, or
notifications/. This file exists to prove the negative case for the
demo — a change to db.py (or anything else in the app) should never
pull this file in as a "dependent," and a query about auth/CRUD
should never recall this file either.

Its own "documents" table is entirely local to this module.
"""

from typing import Dict, List, Tuple
import re

_DOCUMENTS: Dict[int, str] = {}
_next_id = 1


def index_document(text: str) -> int:
    global _next_id
    doc_id = _next_id
    _DOCUMENTS[doc_id] = text
    _next_id += 1
    return doc_id


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _score(query_tokens: List[str], doc_tokens: List[str]) -> float:
    if not doc_tokens:
        return 0.0
    overlap = sum(1 for t in query_tokens if t in doc_tokens)
    return overlap / len(set(query_tokens)) if query_tokens else 0.0


def retrieve(query: str, top_k: int = 3) -> List[Tuple[int, float, str]]:
    """Naive bag-of-words retrieval over the local document store."""
    query_tokens = _tokenize(query)
    scored = []
    for doc_id, text in _DOCUMENTS.items():
        score = _score(query_tokens, _tokenize(text))
        if score > 0:
            scored.append((doc_id, score, text))
    scored.sort(key=lambda row: row[1], reverse=True)
    return scored[:top_k]


def clear_index() -> None:
    _DOCUMENTS.clear()
