"""
JWT auth for protecting backend endpoints from direct access.

BACKEND_AUTH_SECRET must be set in both Cloud Run and Vercel env vars.
If it's not set (local dev), auth is skipped entirely.
"""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Query, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_SECRET = os.getenv("BACKEND_AUTH_SECRET")
_bearer = HTTPBearer(auto_error=False)


def _decode(token: str) -> None:
    try:
        jwt.decode(token, _SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """FastAPI dependency for HTTP endpoints."""
    if not _SECRET:
        return  # auth disabled in local dev
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token.")
    _decode(credentials.credentials)


def create_token() -> str:
    """Issue a 24h JWT signed with BACKEND_AUTH_SECRET. Returns a dummy token in local dev."""
    if not _SECRET:
        return "dev-token"
    return jwt.encode(
        {"sub": "invited", "exp": datetime.now(tz=timezone.utc) + timedelta(hours=24)},
        _SECRET,
        algorithm="HS256",
    )


def verify_ws_token(token: str) -> bool:
    """Call before accepting a WebSocket. Returns True if allowed."""
    if not _SECRET:
        return True
    try:
        jwt.decode(token, _SECRET, algorithms=["HS256"])
        return True
    except jwt.InvalidTokenError:
        return False
