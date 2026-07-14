"""Route-level tests that verify the gating contract across the public app.

We test:
- Public root + admin gates (auth fires before handler hits DB) — fully
  offline.
- Public reads that use `db.fetch_all` — mocked at the import site.
- Public reads that use SQLAlchemy `engine.connect()` directly — these
  require a live MySQL. They are marked as @pytest.mark.requires_db and
  skipped when MYSQL_AVAILABLE is not set or DB is unreachable.
"""
from __future__ import annotations

import os
import socket

import pytest


def _mysql_reachable() -> bool:
    """Cheap TCP probe to skip DB-dependent tests when MySQL is down."""
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


requires_db = pytest.mark.skipif(
    not _mysql_reachable(),
    reason="MySQL not reachable; set DB_HOST/DB_PORT and start MySQL to enable",
)


# These paths use db.fetch_all — mocked below.
PUBLIC_GETS_DB_FETCH = [
    "/api/missing-persons",
    "/api/wanted-criminals",
]

# These paths use SQLAlchemy engine.connect() — need a real DB.
PUBLIC_GETS_DB_ENGINE = [
    "/api/crimes",
    "/api/statistics/summary",
]


@pytest.fixture
def empty_db(monkeypatch):
    """Patch db.fetch_all / fetch_one / execute / insert_and_get_id everywhere
    they were imported, including inside main.py / auth.py / main_admin.py."""
    import db as db_mod
    import main
    import auth as auth_mod
    try:
        import main_admin
        ma = main_admin
    except Exception:
        ma = None

    def empty_fetch_all(*a, **kw):
        return []

    def empty_fetch_one(*a, **kw):
        return None

    def empty_execute(*a, **kw):
        return 0

    empty_insert = lambda *a, **kw: 0

    for mod in (db_mod, main, auth_mod):
        monkeypatch.setattr(mod, "fetch_all", empty_fetch_all, raising=False)
        monkeypatch.setattr(mod, "fetch_one", empty_fetch_one, raising=False)
        monkeypatch.setattr(mod, "execute", empty_execute, raising=False)
        monkeypatch.setattr(mod, "insert_and_get_id", empty_insert, raising=False)

    if ma is not None:
        for fn in ("fetch_all", "fetch_one", "execute", "insert_and_get_id"):
            setattr(ma, fn, {
                "fetch_all": empty_fetch_all,
                "fetch_one": empty_fetch_one,
                "execute": empty_execute,
                "insert_and_get_id": empty_insert,
            }[fn])


@pytest.fixture
def client(empty_db):
    import main  # noqa: F401
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


def test_root_reachable_without_token(client):
    r = client.get("/")
    assert r.status_code != 401


def test_crime_types_reachable_without_token(client):
    r = client.get("/api/crime-types")
    assert r.status_code != 401
    assert r.status_code != 403


def test_districts_reachable_without_token(client):
    r = client.get("/api/districts")
    assert r.status_code != 401
    assert r.status_code != 403


@pytest.mark.parametrize("path", PUBLIC_GETS_DB_FETCH)
def test_public_get_is_reachable_without_token(client, path):
    r = client.get(path)
    assert r.status_code != 401, f"{path} should be public but returned 401"
    assert r.status_code != 403, f"{path} should be public but returned 403"


@pytest.mark.parametrize("path", PUBLIC_GETS_DB_ENGINE)
@requires_db
def test_public_engine_get_is_reachable_without_token(client, path):
    r = client.get(path)
    assert r.status_code != 401, f"{path} should be public but returned 401"
    assert r.status_code != 403, f"{path} should be public but returned 403"


# These paths MUST be gated. Auth fires before handler hits DB, so no mock needed.
GATED_PATHS = [
    ("GET", "/api/admin/users"),
    ("GET", "/api/admin/complaints"),
    ("GET", "/api/admin/emergencies"),
    ("GET", "/api/admin/case-assignments"),
    ("GET", "/api/admin/case-management"),
    ("GET", "/api/admin/activity-log"),
]


@pytest.mark.parametrize("method,path", GATED_PATHS)
def test_admin_route_requires_token(client, method, path):
    r = client.request(method, path)
    assert r.status_code == 401, (
        f"{method} {path} should require auth but returned {r.status_code}"
    )


def test_delete_crime_requires_auth(client):
    r = client.delete("/api/crimes/1")
    assert r.status_code == 401


def test_delete_missing_person_requires_auth(client):
    r = client.delete("/api/missing-persons/1")
    assert r.status_code == 401


def test_chat_send_requires_auth(client):
    r = client.post("/api/chat/send", json={"message": "hi"})
    assert r.status_code == 401


def test_emergency_alert_requires_auth(client):
    r = client.post("/api/emergency-alert", json={})
    assert r.status_code == 401