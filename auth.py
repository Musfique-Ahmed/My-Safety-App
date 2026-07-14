"""Authentication helpers: bcrypt password hashing + JWT issue/decode.

Use:
    from auth import hash_password, verify_password, create_access_token, decode_token
    from auth import get_current_user, require_user, require_admin

Tokens are HS256 with `JWT_SECRET`. `JWT_EXPIRES_MINUTES` controls lifetime.

A token's subject is the `user_id`. On each request, `get_current_user` decodes
the token and refreshes the user row from MySQL via `db.fetch_one`.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from passlib.hash import bcrypt

from db import fetch_one


JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me-please-32bytes")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    """Bcrypt-hash a plaintext password."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be a non-empty string")
    return bcrypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time bcrypt verification."""
    if not password_hash:
        return False
    try:
        return bcrypt.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


# ---------- Tokens ----------

def create_access_token(user_id: int, role: Optional[str] = None) -> str:
    """Issue a signed JWT for `user_id`."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=JWT_EXPIRES_MINUTES)).timestamp()),
    }
    if role:
        payload["role"] = role
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode a JWT or return None if invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# ---------- FastAPI dependencies ----------

def _extract_bearer(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    # Allow raw token without the scheme.
    if len(parts) == 1:
        return parts[0]
    return None


def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Decode the bearer token and load the user row. Raises 401 on failure.

    Public endpoints can leave this dependency out. Admin/write endpoints
    should list it via `Depends(get_current_user)`.
    """
    token = _extract_bearer(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Missing or invalid Authorization header")
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or expired token")
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token subject")

    row = fetch_one(
        "SELECT user_id, username, email, role_hint, status FROM appuser WHERE user_id = %s",
        (user_id,),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User no longer exists")
    if (row.get("status") or "").lower() in {"inactive", "disabled", "banned"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="User account is not active")
    return row


def require_user(user: dict = Depends(get_current_user)) -> dict:
    """Any authenticated, active user."""
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Admin or staff role required."""
    role = (user.get("role_hint") or "").lower()
    if role not in {"admin", "officer", "detective", "staff"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin role required")
    return user
