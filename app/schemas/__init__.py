"""Pydantic request/response models for the MySafety backend.

Each domain gets its own file; this package re-exports the public surface so
handlers can import them with `from app.schemas import ChatMessage, CrimeData, ...`
"""
from app.schemas.auth import (  # noqa: F401
    UserCreate,
    UserLogin,
    UserUpdate,
)
from app.schemas.chat import (  # noqa: F401
    ChatMessage,
)
from app.schemas.crime import (  # noqa: F401
    AdminCrimeCreate,
    CaseAssignment,
    CrimeData,
    StatusUpdate,
)
from app.schemas.emergency import (  # noqa: F401
    EmergencyAlert,
    EmergencyAssignment,
)
from app.schemas.missing import (  # noqa: F401
    MissingPersonFinderUpdate,
    PoliceStationCreate,
)
from app.schemas.wanted import (  # noqa: F401
    CriminalSighting,
    WantedCriminalCreate,
)