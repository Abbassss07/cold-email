"""Session-based authentication using HTTP-only signed cookies."""
from __future__ import annotations

import os
import secrets

import bcrypt
from fastapi import Cookie, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from database import get_setting, set_setting

SESSION_COOKIE = "sdu_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

_serializer: URLSafeTimedSerializer | None = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        secret = os.environ.get("SECRET_KEY", "")
        if not secret or len(secret) < 16:
            raise RuntimeError("SECRET_KEY env var must be set and >= 16 chars")
        _serializer = URLSafeTimedSerializer(secret, salt="sdu-session")
    return _serializer


def create_session_cookie(response: Response, user: str = "admin") -> None:
    token = _get_serializer().dumps({"user": user})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="none", secure=True)


def require_session(sdu_session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> str:
    if not sdu_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = _get_serializer().loads(sdu_session, max_age=SESSION_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return data.get("user", "admin")


async def verify_password(password: str) -> bool:
    """Verify the persisted password, falling back to the bootstrap env value."""
    password_hash = await get_setting("admin_password_hash")
    if password_hash:
        try:
            return bcrypt.checkpw(password.encode(), password_hash.encode())
        except ValueError:
            return False
    expected = os.environ.get("ADMIN_PASSWORD", "")
    return bool(expected) and secrets.compare_digest(password, expected)


async def set_password(password: str) -> None:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    await set_setting("admin_password_hash", password_hash)
