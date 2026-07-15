"""Backward-compat shim.

The real FastAPI app lives at `app.main:app` now. This file exists so any
test, script, or tool that still does `from main import app` keeps working
without changes. New code should import from the `app.*` package directly.
"""
from app.main import app  # noqa: F401