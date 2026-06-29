"""Session-based authentication using HTTP-only signed cookies."""
from __future__ import annotations

import os
from fastapi import Cookie, HTTPException, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

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


def verify_password(password: str) -> bool:
    expected = os.environ.get("ADMIN_PASSWORD", "")
    if not expected:
        return False
    # constant-time compare
    if len(password) != len(expected):
        return False
    result = 0
    for a, b in zip(password, expected):
        result |= ord(a) ^ ord(b)
    return result == 0
