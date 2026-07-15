"""Emergency / panic-button Pydantic models."""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel


class EmergencyAlert(BaseModel):
    user_id: Optional[int] = None
    location: Optional[Dict[str, Any]] = None
    address_label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    alert_type: str
    description: str
    severity: str = "High"


class EmergencyAssignment(BaseModel):
    officer_id: int