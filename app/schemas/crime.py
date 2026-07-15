"""Crime / case-management Pydantic models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CrimeData(BaseModel):
    location: dict
    crime: dict
    victim: Optional[dict] = None
    criminal: Optional[dict] = None
    weapon: Optional[dict] = None
    witness: Optional[dict] = None
    # New optional fields collected by the frontend
    reporter_id: Optional[str] = None
    incident_date: Optional[str] = None
    evidence_files: Optional[List[dict]] = None


class AdminCrimeCreate(BaseModel):
    crime_type: str
    status: str
    city: str
    area_name: str
    description: str
    incident_time: Optional[str] = None
    priority: Optional[str] = "medium"
    location_details: Optional[str] = None
    reporter_id: Optional[int] = None
    victim: Optional[Dict[str, Any]] = None
    criminal: Optional[Dict[str, Any]] = None
    weapon: Optional[Dict[str, Any]] = None
    witness: Optional[Dict[str, Any]] = None
    evidence_files: Optional[List[Dict[str, Any]]] = None
    witness_info: Optional[str] = None


class CaseAssignment(BaseModel):
    user_id: int
    crime_id: int
    duty_role: str


class StatusUpdate(BaseModel):
    new_status: str
    notes: Optional[str] = None
    changed_by: Optional[int] = None