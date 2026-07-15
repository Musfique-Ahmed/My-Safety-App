"""Wanted-criminal Pydantic models (creation + sighting)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CriminalSighting(BaseModel):
    last_seen_time: str
    last_seen_location: str
    still_with_finder: bool = False
    reporter_contact: Optional[str] = None


class WantedCriminalCreate(BaseModel):
    name: str
    alias: Optional[str] = None
    age_range: str
    gender: str
    description: str
    height: Optional[str] = None
    weight: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    distinguishing_marks: Optional[str] = None
    crimes_committed: str
    reward_amount: Optional[float] = 0
    danger_level: str = "Medium"
    last_known_location: Optional[str] = None
    photo_url: Optional[str] = None
    added_by: int