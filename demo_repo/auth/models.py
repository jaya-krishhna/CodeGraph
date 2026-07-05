"""
auth/models.py — shared auth-related schemas.

Imported by jwt_auth.py (to type the decoded token payload) and by
every module in crud/ (to type the "current user" passed into CRUD
calls for ownership checks).
"""

from typing import Optional
from pydantic import BaseModel


class User(BaseModel):
    id: int
    username: str
    email: str
    hashed_password: str
    is_active: bool = True


class UserOut(BaseModel):
    """Public-facing view of a user, no password hash."""

    id: int
    username: str
    email: str
    is_active: bool = True

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
        )


class TokenData(BaseModel):
    user_id: int
    username: str
    scopes: list[str] = []


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


def new_user(username: str, email: str, hashed_password: str, user_id: Optional[int] = None) -> User:
    return User(
        id=user_id or 0,
        username=username,
        email=email,
        hashed_password=hashed_password,
    )
