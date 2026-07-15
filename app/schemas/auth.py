"""Auth-related Pydantic models: signup, login, user admin updates."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    username: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    user_id: int
    role_hint: Optional[str] = None
    status: Optional[str] = None
    station_id: Optional[int] = None