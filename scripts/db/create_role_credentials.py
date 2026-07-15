"""Create one credential per role and verify each works against the live stack.

Run with:
    python scripts/create_role_credentials.py
"""
import os
import secrets
import sys

import pymysql
import requests

# ---- 1. Load .env ----
with open('.env', encoding='utf-8') as f:
    for line in f:
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        os.environ[k.strip()] = v.strip().strip('"').strip("'")
os.environ.setdefault('JWT_SECRET', 'x' * 64)

DB = dict(
    host=os.environ['DB_HOST'],
    port=int(os.environ['DB_PORT']),
    user=os.environ['DB_USER'],
    password=os.environ.get('DB_PASSWORD', ''),
    database=os.environ['DB_NAME'],
    charset='utf8mb4',
    autocommit=True,
)
BASE = 'http://127.0.0.1:8000'

# ---- 2. Roles (auth.py:127 accepts admin | officer | detective | staff) ----
ROLES = [
    ('admin',     'admin'),
    ('officer',   'officer'),
    ('detective', 'detective'),
    ('staff',     'staff'),
    ('User',      'User'),
]


def _register(role_key):
    nonce = secrets.token_hex(3)
    email = f'{role_key}+{nonce}@mysafety.local'
    password = 'RoleTest-' + role_key.capitalize() + '-' + nonce.upper()
    name = f'{role_key.title()} User'
    r = requests.post(BASE + '/register',
                      json={'email': email, 'username': email.split('+')[0],
                            'password': password,
                            'name': name}, timeout=5)
    if r.status_code != 200:
        raise RuntimeError(f'register failed: {r.status_code} {r.text}')
    j = r.json()
    return {
        'role_key': role_key,
        'role_hint': role_key,
        'email': email,
        'password': password,
        'name': name,
        'user_id': j['user']['user_id'],
        'token': j['token'],
    }


def _login(email, password):
    r = requests.post(BASE + '/login', json={'email': email, 'password': password}, timeout=5)
    if r.status_code != 200:
        raise RuntimeError(f'login failed for {email}: {r.status_code} {r.text}')
    return r.json()['token']


def _admin_probe(token):
    headers = {'Authorization': 'Bearer ' + token}
    r = requests.get(BASE + '/api/admin/users', headers=headers, timeout=5)
    return r.status_code


def main():
    print(f'Creating {len(ROLES)} accounts against {BASE} (db={DB["database"]})...\n')
    created = [_register(rk) for rk, _ in ROLES]

    # Promote the four privileged ones directly in DB
    conn = pymysql.connect(**DB)
    with conn.cursor() as c:
        for u in created:
            if u['role_hint'] != 'User':
                c.execute(
                    "UPDATE appuser SET role_hint=%s, status='active' WHERE user_id=%s",
                    (u['role_hint'], u['user_id']),
                )
    conn.close()

    # Re-login so the JWT reflects the new role_hint
    for u in created:
        u['token'] = _login(u['email'], u['password'])

    # Probe each role
    for u in created:
        u['admin_probe'] = _admin_probe(u['token'])
        headers = {'Authorization': 'Bearer ' + u['token']}
        r = requests.post(BASE + '/api/chat/send', headers=headers,
                          json={'user_id': u['user_id'],
                                'message': f'hi from {u["role_hint"]}',
                                'is_admin': False},
                          timeout=5)
        u['chat_send'] = r.status_code

    # ---- Print + write to CREDENTIALS.txt ----
    print('=' * 78)
    print(' CREDENTIALS — save these. Passwords are random; only displayed once.')
    print('=' * 78)
    for u in created:
        is_priv = u['role_hint'] != 'User'
        if is_priv and u['admin_probe'] == 200:
            verdict = 'admin gate PASSED (allowed, as expected)'
        elif (not is_priv) and u['admin_probe'] == 403:
            verdict = 'admin gate BLOCKED (correct: user has no admin role)'
        else:
            verdict = f"unexpected admin probe result: {u['admin_probe']}"
        print(f'-- ROLE: {u["role_hint"]:<10} --')
        print(f'   email    : {u["email"]}')
        print(f'   password : {u["password"]}')
        print(f'   user_id  : {u["user_id"]}')
        print(f'   token    : {u["token"][:32]}...')
        print(f'   GET /api/admin/users -> {u["admin_probe"]}')
        print(f'   POST /api/chat/send  -> {u["chat_send"]}')
        print(f'   verdict   : {verdict}')
        print()

    out_path = os.path.abspath('CREDENTIALS.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('My Safety - Local credentials\n')
        f.write('=' * 60 + '\n')
        f.write(f'Base URL: {BASE}\n')
        f.write(f'Database: MariaDB 12.3 on {DB["host"]}:{DB["port"]} db={DB["database"]}\n\n')
        for u in created:
            f.write(f'-- ROLE: {u["role_hint"]} --\n')
            f.write(f'  email     : {u["email"]}\n')
            f.write(f'  password  : {u["password"]}\n')
            f.write(f'  user_id   : {u["user_id"]}\n')
            f.write(f'  JWT token : {u["token"]}\n')
            f.write(f'  admin gate probes: {u["admin_probe"]}\n')
            f.write(f'  chat send status : {u["chat_send"]}\n\n')
    print(f'Full credentials written to: {out_path}')


if __name__ == '__main__':
    main()
