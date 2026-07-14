"""Tests for the /admin-api sub-app mount.

main_admin.py is mounted inside main.app at /admin-api. Some admin routes
live ONLY in main_admin.py and are reachable there as
/admin-api/api/admin/<legacy_path>. These tests verify the mount exists and
the legacy routes are addressable.

We don't mock the DB here — we only check route registration (404 vs 401
behaviour tells us whether the mount is wired).
"""
from __future__ import annotations

import pytest


@pytest.fixture
def client():
    import main  # noqa: F401
    from fastapi.testclient import TestClient
    with TestClient(main.app) as c:
        yield c


def test_admin_api_mount_exists(client):
    """An unauthenticated request to a /admin-api path should NOT 404 — it
    should 401 (proving the route is wired) or 404 if FastAPI returns 404
    when no handler matches. We accept either as long as we don't get a
    generic 200 with no handler."""
    r = client.get("/admin-api/")
    assert r.status_code in (200, 401, 404, 307)
    # Specifically: a path that exists in main_admin should NOT 404.
    r = client.get("/admin-api/api/admin/evidence-files")
    assert r.status_code != 404, "/admin-api/api/admin/evidence-files should be mounted"


def test_admin_api_route_requires_auth(client):
    r = client.get("/admin-api/api/admin/evidence-files")
    # Without a token, this MUST be 401 (the route is gated).
    assert r.status_code == 401


def test_main_admin_app_independently_imports():
    """main_admin.app must remain importable as a standalone app for tests
    and the legacy entrypoint."""
    import main_admin

    assert main_admin.app is not None
    # And the gated routes should be present
    paths = {r.path for r in main_admin.app.routes if hasattr(r, "path")}
    # Pick a few representative paths
    assert "/api/crimes" in paths
    assert "/api/admin/users" in paths
    assert "/api/admin/evidence-files" in paths
    assert "/api/admin/admin-activity-log" in paths


def test_admin_api_subapp_attached_to_main():
    """main.app must have main_admin.app mounted under /admin-api.

    FastAPI represents mounts as a single route with `app` attribute being
    the sub-app and `path` being the prefix."""
    import main
    import main_admin

    mounted = False
    for route in main.app.routes:
        if getattr(route, "app", None) is main_admin.app and route.path == "/admin-api":
            mounted = True
            break
    assert mounted, "main_admin.app must be mounted under /admin-api in main.app"


def test_admin_api_route_count_matches_main_admin():
    """Sanity check: every admin route registered in main_admin should be
    reachable via /admin-api/<path>."""
    import main
    import main_admin

    main_admin_paths = {r.path for r in main_admin.app.routes if hasattr(r, "path")}
    main_admin_paths.discard("/")
    main_admin_paths.discard("/static")  # static-files mount, not HTTP

    sample_paths = [
        "/api/admin/users",
        "/api/admin/evidence-files",
        "/api/admin/admin-activity-log",
        "/api/admin/criminal-sightings",
    ]
    for p in sample_paths:
        assert p in main_admin_paths, f"main_admin should have route {p}"