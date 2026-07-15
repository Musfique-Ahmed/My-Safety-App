"""Chat-related Pydantic models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    user_id: int
    message: str
    report_id: Optional[str] = None
    is_admin: Optional[bool] = False