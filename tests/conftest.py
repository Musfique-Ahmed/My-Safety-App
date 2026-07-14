"""Pytest fixtures shared across the suite.

Sets JWT_SECRET before any module reads it, and provides:
- client: a FastAPI TestClient bound to main.app
- admin_client: same client but with a pre-baked admin Authorization header
"""
from __future__ import annotations

import os

# Configure env BEFORE any project module reads os.getenv.
os.environ.setdefault("JWT_SECRET", "pytest-secret-do-not-use-in-prod-32b")
os.environ.setdefault("JWT_EXPIRES_MINUTES", "60")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient for the main app.

    We don't spin up a real DB; tests that need DB rows use the mock_db
    fixture to monkey-patch db.fetch_one / db.fetch_all.
    """
    # Import inside the fixture so env vars are already set.
    import main  # noqa: F401  -- ensures app is constructed

    from main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_token():
    """A signed JWT for an admin user (does NOT verify against a DB)."""
    from auth import create_access_token

    return create_access_token(user_id=999, role="admin")


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_token():
    from auth import create_access_token

    return create_access_token(user_id=42, role="user")


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def mock_db_user(monkeypatch):
    """Replace db.fetch_one so get_current_user can resolve a user without
    a real database. Returns a dict so tests can assert what was loaded."""
    import db as db_mod

    captured = {}

    def fake_fetch_one(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return {
            "user_id": params[0] if params else None,
            "username": "tester",
            "email": "tester@example.com",
            "role_hint": "admin",
            "status": "active",
        }

    monkeypatch.setattr(db_mod, "fetch_one", fake_fetch_one)
    return captured