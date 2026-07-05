"""
auth/jwt_auth.py — token issuing + verification.

Imports:
  - auth.models (User, TokenData, Token)
  - db (to look up the user record a token claims to belong to)
"""

import time
import hashlib
import hmac
import json
import base64
from typing import Optional

import os
from dotenv import load_dotenv

from auth.models import User, TokenData, Token
from db import get_db

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
EXPIRE_SECONDS = int(os.getenv("EXPIRE_SECONDS"))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_access_token(user: User) -> Token:
    header = _b64url(json.dumps({"alg": ALGORITHM, "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps(
            {
                "user_id": user.id,
                "username": user.username,
                "exp": int(time.time()) + EXPIRE_SECONDS,
            }
        ).encode()
    )
    signature = _b64url(
        hmac.new(SECRET_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    )
    return Token(access_token=f"{header}.{payload}.{signature}")


def decode_token(token: str) -> Optional[TokenData]:
    try:
        header, payload, _signature = token.split(".")
        data = json.loads(base64.urlsafe_b64decode(payload + "=="))
        if data["exp"] < time.time():
            return None
        return TokenData(user_id=data["user_id"], username=data["username"])
    except Exception:
        return None


def authenticate_user(username: str, password_hash: str) -> Optional[User]:
    db = get_db()
    matches = db.find_by("users", username=username, hashed_password=password_hash)
    if not matches:
        return None
    return User(**matches[0])
