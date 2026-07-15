"""Missing-person finder + police-station Pydantic models."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, validator


class MissingPersonFinderUpdate(BaseModel):
    finding_location: str
    finder_name: str
    finder_phone: str
    finder_email: Optional[str] = None
    still_with_finder: Optional[bool] = False

    @validator("finding_location", "finder_name", "finder_phone")
    def validate_non_empty(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("Field cannot be empty")
        return str(value).strip()

    @validator("finder_email")
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class PoliceStationCreate(BaseModel):
    station_name: str
    station_code: str
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    jurisdiction_area: Optional[str] = None
    officer_in_charge: Optional[str] = None

    @validator("latitude")
    def validate_latitude(cls, value):
        if value is None:
            return value
        if not (-90.0 <= value <= 90.0):
            raise ValueError("Latitude must be between -90 and 90 degrees")
        return value

    @validator("longitude")
    def validate_longitude(cls, value):
        if value is None:
            return value
        if not (-180.0 <= value <= 180.0):
            raise ValueError("Longitude must be between -180 and 180 degrees")
        return value