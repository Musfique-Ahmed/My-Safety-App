"""Project-wide constants and paths.

`BASE_DIR` is the repository root — used by `StaticFiles` mounts and the
HTML page handlers under `app/api/routers/pages.py` to read templates
without depending on the current working directory.

JWT secret / TTL live here too so they can be imported by both the
security helpers and tests that need to read or override them.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
STATIC_DIR: Path = BASE_DIR / "static"
TEMPLATES_DIR: Path = STATIC_DIR / "templates"
CONTENTS_DIR: Path = STATIC_DIR / "contents"
UPLOADS_DIR: Path = STATIC_DIR / "uploads"
ASSETS_DIR: Path = STATIC_DIR / "assets"

JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-only-change-me-please-32bytes")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))
