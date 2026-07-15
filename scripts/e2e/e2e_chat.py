"""End-to-end test of the chat feature.

Drives two users (citizen + admin) through:
    register citizen -> register admin -> promote admin -> send msgs ->
    list conversations -> fetch history -> verify persistence.

Run after starting uvicorn on the port in E2E_BASE.
"""
from __future__ import annotations

import os
import sys
import time

import pymysql
import requests


BASE = os.getenv("E2E_BASE", "http://127.0.0.1:8767")
TIMEOUT = 5


def _check(label: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label}" + (f": {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


def _register(sess: requests.Session, email: str, password: str, name: str) -> tuple[int, str]:
    r = sess.post(BASE + "/register", json={
        "username": email.split("@")[0],
        "email": email,
        "password": password,
        "full_name": name,
    }, timeout=TIMEOUT)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    body = r.json()
    return body["user"]["user_id"], body["token"]


def _promote_admin(user_id: int) -> None:
    db = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3307")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpw"),
        database=os.getenv("DB_NAME", "mysafetydb"),
    )
    try:
        with db.cursor() as cur:
            cur.execute(
                "UPDATE appuser SET role_hint='admin', status='active' WHERE user_id=%s",
                (user_id,),
            )
        db.commit()
    finally:
        db.close()


def main() -> None:
    suffix = str(int(time.time()))
    citizen_email = f"citizen+{suffix}@example.com"
    admin_email = f"chatadmin+{suffix}@example.com"
    password = "ChatTest123!"

    # Use a separate session per user so cookies/headers don't bleed.
    citizen_sess = requests.Session()
    admin_sess = requests.Session()

    # 1. /api/chat/send requires auth (no token -> 401)
    r = requests.post(BASE + "/api/chat/send",
                      json={"user_id": 1, "message": "hi"},
                      timeout=TIMEOUT)
    _check("POST /api/chat/send (no token) -> 401", r.status_code == 401,
           f"status {r.status_code}")

    # 2. Register both users
    citizen_id, citizen_token = _register(citizen_sess, citizen_email, password, "Citizen User")
    print(f"   citizen registered: user_id={citizen_id}")
    admin_id, admin_token = _register(admin_sess, admin_email, password, "Chat Admin")
    print(f"   admin registered:   user_id={admin_id}")

    # 3. Promote admin to admin role
    _promote_admin(admin_id)
    print(f"   promoted user_id={admin_id} to admin")

    # 4. Citizen sends a message
    r = citizen_sess.post(BASE + "/api/chat/send",
                          json={"user_id": citizen_id,
                                "message": "Hello, I need help with my missing person report"},
                          headers={"Authorization": f"Bearer {citizen_token}"},
                          timeout=TIMEOUT)
    _check("citizen POST /api/chat/send", r.status_code == 200,
           f"status {r.status_code} body {r.text[:200]}")
    body = r.json()
    citizen_msg_id = body.get("message_id")
    assert citizen_msg_id, f"no message_id in response: {body}"
    print(f"   citizen message_id={citizen_msg_id}")

    # 5. Admin replies (is_admin=true; admin role lets this through)
    r = admin_sess.post(BASE + "/api/chat/send",
                        json={"user_id": admin_id,
                              "message": "Hi citizen, can you share more details?",
                              "is_admin": True},
                        headers={"Authorization": f"Bearer {admin_token}"},
                        timeout=TIMEOUT)
    _check("admin POST /api/chat/send (is_admin=true)", r.status_code == 200,
           f"status {r.status_code} body {r.text[:200]}")
    body = r.json()
    admin_msg_id = body.get("message_id")
    print(f"   admin message_id={admin_msg_id}")

    # 6. Non-admin tries to send is_admin=true (should be downgraded to user)
    r = citizen_sess.post(BASE + "/api/chat/send",
                          json={"user_id": citizen_id,
                                "message": "trying to impersonate admin",
                                "is_admin": True},
                          headers={"Authorization": f"Bearer {citizen_token}"},
                          timeout=TIMEOUT)
    _check("citizen POST /api/chat/send (is_admin=true) -> 200 but downgraded",
           r.status_code == 200, f"status {r.status_code}")

    # 7. Verify the impersonation attempt was downgraded by inspecting the row
    db = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3307")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "rootpw"),
        database=os.getenv("DB_NAME", "mysafetydb"),
    )
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT is_admin FROM chat_messages WHERE message_id=%s",
                (citizen_msg_id + 2,),  # the impersonation message
            )
            row = cur.fetchone()
            assert row is not None, "impersonation message not found"
            _check("non-admin is_admin flag was downgraded to 0", row[0] == 0,
                   f"is_admin={row[0]}")

            # 8. Verify the admin's reply was stored with is_admin=1
            cur.execute(
                "SELECT is_admin, message FROM chat_messages WHERE message_id=%s",
                (admin_msg_id,),
            )
            row = cur.fetchone()
            assert row is not None, "admin message not found"
            _check("admin is_admin flag persisted as 1", row[0] == 1,
                   f"is_admin={row[0]}")
            print(f"   admin message: {row[1][:50]}...")
    finally:
        db.close()

    # 9. GET /api/chat/messages lists recent messages
    r = citizen_sess.get(BASE + "/api/chat/messages?limit=10",
                         headers={"Authorization": f"Bearer {citizen_token}"},
                         timeout=TIMEOUT)
    _check("GET /api/chat/messages", r.status_code == 200,
           f"status {r.status_code} body {r.text[:200]}")
    body = r.json()
    msgs = body if isinstance(body, list) else body.get("messages") or body.get("data") or []
    _check("GET /api/chat/messages includes our 3 messages",
           len(msgs) >= 3, f"got {len(msgs)} msgs")

    # 10. GET /api/chat/user-conversations/{user_id}
    r = citizen_sess.get(BASE + f"/api/chat/user-conversations/{citizen_id}",
                         headers={"Authorization": f"Bearer {citizen_token}"},
                         timeout=TIMEOUT)
    _check("GET /api/chat/user-conversations/{user_id}",
           r.status_code == 200, f"status {r.status_code} body {r.text[:200]}")

    # 11. GET /api/chat/conversation/{other_user_id} fetches the thread
    r = citizen_sess.get(BASE + f"/api/chat/conversation/{admin_id}",
                         headers={"Authorization": f"Bearer {citizen_token}"},
                         timeout=TIMEOUT)
    _check("GET /api/chat/conversation/{user_id}",
           r.status_code == 200, f"status {r.status_code} body {r.text[:200]}")

    # 12. POST /api/chat/messages (the other endpoint) — should also be gated
    r = requests.post(BASE + "/api/chat/messages",
                      json={"user_id": 1, "message": "hi"},
                      timeout=TIMEOUT)
    _check("POST /api/chat/messages (no token) -> 401", r.status_code == 401,
           f"status {r.status_code}")

    print("\nALL CHAT E2E CHECKS PASSED")


if __name__ == "__main__":
    main()