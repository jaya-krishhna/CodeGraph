"""
auth/dependencies.py — FastAPI dependency-injection helpers.

Imports:
  - auth.jwt_auth (to decode bearer tokens)
  - auth.models (User, UserOut, TokenData)
  - db (to load the full user record for the decoded token)
"""

from typing import Optional

from auth.jwt_auth import decode_token
from auth.models import User, UserOut, TokenData
from db import get_db


class AuthError(Exception):
    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def get_token_data(authorization_header: Optional[str]) -> TokenData:
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise AuthError("Missing or malformed Authorization header")

    token = authorization_header.removeprefix("Bearer ").strip()
    token_data = decode_token(token)
    if token_data is None:
        raise AuthError("Invalid or expired token")
    return token_data


def get_current_user(authorization_header: Optional[str]) -> UserOut:
    token_data = get_token_data(authorization_header)
    db = get_db()
    record = db.get("users", token_data.user_id)
    if record is None:
        raise AuthError("User no longer exists", status_code=404)

    user = User(**record)
    if not user.is_active:
        raise AuthError("User account is disabled", status_code=403)

    return UserOut.from_user(user)


def require_active_user(authorization_header: Optional[str]) -> UserOut:
    """Thin wrapper kept separate so routes can express intent clearly."""
    return get_current_user(authorization_header)
