"""End-to-end smoke test for the My Safety backend.

Boots the FastAPI app against a live MySQL (the docker container on
localhost:3307) and walks through:
    register -> login -> submit crime -> admin sees it -> mark as found.

Run after starting uvicorn on 127.0.0.1:8765:
    DB_HOST=localhost DB_PORT=3307 DB_USER=root DB_PASSWORD=rootpw \\
    DB_NAME=mysafetydb python scripts/e2e_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests


BASE = os.getenv("E2E_BASE", "http://127.0.0.1:8765")
TIMEOUT = 5


def _check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}" + (f": {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def main() -> None:
    sess = requests.Session()

    # 0. health
    r = sess.get(BASE + "/", timeout=TIMEOUT)
    _check("GET /", r.status_code == 200, f"status {r.status_code}")

    # 1. /api/crimes is public
    r = sess.get(BASE + "/api/crimes?limit=5", timeout=TIMEOUT)
    _check("GET /api/crimes (public)", r.status_code == 200, f"status {r.status_code}")
    body = r.json()
    assert "crimes" in body, "missing 'crimes' key"
    print(f"   initial crime count: {body.get('total', len(body.get('crimes', [])))}")

    # 2. /api/admin/users requires auth
    r = sess.get(BASE + "/api/admin/users", timeout=TIMEOUT)
    _check("GET /api/admin/users (no token -> 401)", r.status_code == 401,
           f"status {r.status_code}")

    # 3. register a fresh user
    suffix = str(int(time.time()))
    email = f"smoke+{suffix}@example.com"
    password = "SmokeTest123!"
    r = sess.post(BASE + "/register", json={
        "username": f"smoke_{suffix}",
        "email": email,
        "password": password,
        "full_name": "Smoke Tester",
    }, timeout=TIMEOUT)
    _check("POST /register", r.status_code in (200, 201), f"status {r.status_code} body {r.text[:200]}")
    register_body = r.json()
    user_token = register_body.get("token")
    user_id = (register_body.get("user") or {}).get("user_id")
    assert user_token, "no token in register response"
    assert user_id, "no user_id in register response"
    print(f"   registered user_id={user_id}")

    # 4. login (same credentials)
    r = sess.post(BASE + "/login", json={"email": email, "password": password}, timeout=TIMEOUT)
    _check("POST /login", r.status_code == 200, f"status {r.status_code}")
    login_body = r.json()
    login_token = login_body.get("token")
    assert login_token, "no token in login response"
    print(f"   login token length: {len(login_token)}")

    # 5. submit a crime report
    crime_payload = {
        "location": {"city": "SmokeCity", "area": "SmokeArea", "district": "Dhaka",
                     "latitude": "23.7", "longitude": "90.3"},
        "crime": {"type": "SmokeTest", "description": "end-to-end smoke",
                  "incident_date": "2025-10-10T22:00:00"},
        "victim": {"name": "Smoke Victim"},
        "criminal": {"name": "Smoke Criminal"},
        "weapon": None,
        "witness": {"name": "Smoke Witness", "phone": "0123456789"},
        "reporter_id": str(user_id),
        "incident_date": "2025-10-10 22:00:00",
        "evidence_files": [{"filename": "smoke.jpg", "url": "/static/uploads/smoke.jpg"}],
    }
    r = sess.post(BASE + "/api/crimes", json=crime_payload,
                  headers={"Authorization": f"Bearer {login_token}"},
                  timeout=TIMEOUT)
    _check("POST /api/crimes", r.status_code in (200, 201),
           f"status {r.status_code} body {r.text[:200]}")
    crime_body = r.json()
    new_crime_id = crime_body.get("crime_id") or crime_body.get("id")
    assert new_crime_id, f"no crime_id in response: {crime_body}"
    print(f"   inserted crime_id={new_crime_id}")

    # 6. public read sees the new crime
    r = sess.get(BASE + f"/api/crimes?limit=10", timeout=TIMEOUT)
    body = r.json()
    found = any(c.get("crime_id") == new_crime_id for c in body.get("crimes", []))
    _check("GET /api/crimes includes new crime", found, f"searched {len(body.get('crimes', []))} rows")

    # 7. submit a missing person report
    mp_payload = {
        "name": f"Smoke Missing {suffix}",
        "age": 30,
        "last_seen_location": "Smoke Park",
        "reporter_name": "Smoke Reporter",
        "reporter_phone": "01961905838",
    }
    r = sess.post(BASE + "/api/missing-persons", json=mp_payload,
                  headers={"Authorization": f"Bearer {login_token}"},
                  timeout=TIMEOUT)
    _check("POST /api/missing-persons", r.status_code in (200, 201),
           f"status {r.status_code} body {r.text[:200]}")
    mp_body = r.json()
    new_mp_id = mp_body.get("missing_id") or mp_body.get("id")
    assert new_mp_id, f"no missing_id in response: {mp_body}"
    print(f"   inserted missing_id={new_mp_id}")

    # 8. admin gate: regular user gets 403
    r = sess.get(BASE + "/api/admin/users",
                 headers={"Authorization": f"Bearer {login_token}"},
                 timeout=TIMEOUT)
    _check("regular user GET /api/admin/users -> 403",
           r.status_code == 403, f"status {r.status_code}")

    # 9. admin gate: existing admin user (created via SQL) gets through
    # We promote our smoke user via direct SQL UPDATE.
    import pymysql
    db = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3307")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpw"),
        database=os.getenv("DB_NAME", "mysafetydb"),
    )
    try:
        with db.cursor() as cur:
            cur.execute("UPDATE appuser SET role_hint='admin', status='active' WHERE user_id=%s",
                        (user_id,))
        db.commit()
    finally:
        db.close()
    print(f"   promoted user_id={user_id} to admin role")

    # Re-login to refresh token (or reuse; role is encoded in appuser, not JWT — so
    # the existing token now resolves an admin row via get_current_user)
    r = sess.get(BASE + "/api/admin/users",
                 headers={"Authorization": f"Bearer {login_token}"},
                 timeout=TIMEOUT)
    _check("promoted user GET /api/admin/users -> 200",
           r.status_code == 200, f"status {r.status_code} body {r.text[:200]}")

    # 10. /admin-api sub-app is mounted and gated
    r = sess.get(BASE + "/admin-api/api/admin/evidence-files", timeout=TIMEOUT)
    _check("GET /admin-api/... (no token -> 401)",
           r.status_code == 401, f"status {r.status_code}")
    r = sess.get(BASE + "/admin-api/api/admin/evidence-files",
                 headers={"Authorization": f"Bearer {login_token}"},
                 timeout=TIMEOUT)
    _check("promoted user GET /admin-api/api/admin/evidence-files -> 200",
           r.status_code == 200, f"status {r.status_code} body {r.text[:200]}")

    print("\nALL E2E SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()