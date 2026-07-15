"""My-Safety-App backend package.

Re-exports the FastAPI `app` so a single `import app` (or
`uvicorn app:app`) is enough to boot the server. All real work
lives in `app.main`; this file is purely a convenience shim.
"""
from app.main import app  # noqa: F401

__all__ = ["app"]
