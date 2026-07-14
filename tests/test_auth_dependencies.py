"""Tests for FastAPI dependency factories: get_current_user, require_user,
require_admin. Uses TestClient + a mocked auth.fetch_one and a mocked
SQLAlchemy engine so no real MySQL is needed.
"""
from __future__ import annotations

import pytest

from auth import create_access_token


class _FakeConn:
    """Minimal SQLAlchemy connection stand-in. context-manager safe."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args, **kwargs):
        return _FakeResult()


class _FakeResult:
    def mappings(self):
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return None


@pytest.fixture
def patch_user(monkeypatch):
    """Mock auth + main's DB access so admin routes don't touch MySQL."""
    import auth as auth_mod
    import db as db_mod
    import main

    state = {"called": 0, "user": None}

    def fake(sql, params=None):
        state["called"] += 1
        return state["user"]

    monkeypatch.setattr(auth_mod, "fetch_one", fake)
    monkeypatch.setattr(db_mod, "fetch_one", fake)
    monkeypatch.setattr(db_mod, "fetch_all", lambda *a, **kw: [])
    monkeypatch.setattr(db_mod, "execute", lambda *a, **kw: 0)
    monkeypatch.setattr(db_mod, "insert_and_get_id", lambda *a, **kw: 0)

    # Patches on main (it did `from db import ...`)
    for name, replacement in (
        ("fetch_one", fake),
        ("fetch_all", lambda *a, **kw: []),
        ("execute", lambda *a, **kw: 0),
        ("insert_and_get_id", lambda *a, **kw: 0),
    ):
        if hasattr(main, name):
            monkeypatch.setattr(main, name, replacement)
    # Replace the SQLAlchemy engine used by main routes
    if hasattr(main, "engine"):
        monkeypatch.setattr(main.engine, "connect", lambda *a, **kw: _FakeConn())

    def _set(user):
        state["user"] = user

    return _set, state


class TestAuthDependency:
    def test_missing_header_returns_401(self, patch_user):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        with TestClient(main.app) as c:
            r = c.get("/api/admin/users")
            assert r.status_code == 401

    def test_malformed_header_returns_401(self, patch_user):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        with TestClient(main.app) as c:
            r = c.get("/api/admin/users", headers={"Authorization": "Garbage"})
            assert r.status_code == 401

    def test_invalid_token_returns_401(self, patch_user):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        with TestClient(main.app) as c:
            r = c.get(
                "/api/admin/users",
                headers={"Authorization": "Bearer not.a.real.jwt"},
            )
            assert r.status_code == 401

    def test_valid_token_loads_user(self, patch_user):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, state = patch_user
        _set({
            "user_id": 7, "username": "x", "email": "x@x",
            "role_hint": "admin", "status": "active",
        })
        with TestClient(main.app) as c:
            tok = create_access_token(user_id=7, role="admin")
            r = c.get("/api/admin/users", headers={"Authorization": f"Bearer {tok}"})
            assert r.status_code != 401, r.text
            assert state["called"] >= 1


class TestAdminRoleEnforcement:
    @pytest.mark.parametrize("role", ["user", "guest", "", "anonymous"])
    def test_non_admin_role_is_forbidden(self, patch_user, role):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        _set({
            "user_id": 1, "username": "x", "email": "x@x",
            "role_hint": role, "status": "active",
        })
        with TestClient(main.app) as c:
            tok = create_access_token(user_id=1, role=role or "user")
            r = c.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 403, r.text
            assert "Admin" in r.json()["detail"]

    @pytest.mark.parametrize("role", ["admin", "officer", "detective", "staff"])
    def test_admin_role_passes_auth_gate(self, patch_user, role):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        _set({
            "user_id": 1, "username": "x", "email": "x@x",
            "role_hint": role, "status": "active",
        })
        with TestClient(main.app) as c:
            tok = create_access_token(user_id=1, role=role)
            r = c.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code != 403, r.text


class TestInactiveUser:
    def test_disabled_user_is_forbidden(self, patch_user):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        _set({
            "user_id": 1, "username": "x", "email": "x@x",
            "role_hint": "admin", "status": "disabled",
        })
        with TestClient(main.app) as c:
            tok = create_access_token(user_id=1, role="admin")
            r = c.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 403

    def test_missing_user_returns_401(self, patch_user):
        import main  # noqa: F401
        from fastapi.testclient import TestClient
        _set, _state = patch_user
        _set(None)
        with TestClient(main.app) as c:
            tok = create_access_token(user_id=999, role="admin")
            r = c.get(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 401