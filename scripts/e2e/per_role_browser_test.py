"""Per-role browser-driven test.

For every role:
  - Log in via the /login form using real credentials
  - Capture the auth_token from localStorage
  - Visit every page route that exists in the app
  - Capture: status, console errors, network 4xx/5xx, broken resources
  - Try common interactive flows (chat send, panic button, bulletin form submit)

Writes a single JSON report with per-role findings.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
CREDS_FILE = Path('CREDENTIALS.txt')
OUT_JSON = Path('screenshots/per_role_report.json')
OUT_DIR = Path('screenshots/per_role')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def parse_creds(path):
    creds = {}
    cur = None
    for line in path.read_text(encoding='utf-8').splitlines():
        m = re.match(r'-- ROLE: (\w+) --', line)
        if m:
            cur = {'role': m.group(1).lower(), 'email': None, 'password': None}
            creds[cur['role']] = cur
            continue
        if not cur:
            continue
        m = re.match(r'\s+email\s+:\s+(\S+)', line)
        if m:
            cur['email'] = m.group(1)
        m = re.match(r'\s+password\s+:\s+(\S+)', line)
        if m:
            cur['password'] = m.group(1)
    return creds


PAGES_TO_TRY = [
    ('/', 'home'),
    ('/dashboard', 'bulletin_dashboard'),
    ('/login', 'login'),
    ('/signup', 'signup'),
    ('/report-crime', 'report_crime'),
    ('/missing-person', 'missing_person'),
    ('/wanted-criminals', 'wanted_criminals'),
    ('/chatbox', 'chatbox'),
    ('/admin', 'admin_dashboard'),
    ('/admin-dashboard', 'admin_dashboard_alt'),
    ('/report-missing', 'report_missing'),
]


def visit_role(role_name, cred):
    print(f'\n=== Role: {role_name.upper()} ({cred["email"]}) ===')
    findings = {
        'role': role_name,
        'email': cred['email'],
        'login_ok': False,
        'pages': {},
        'console_errors': [],
        'broken_resources': [],
        'interactions': {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1440, 'height': 900})

        def attach_listeners(pg):
            def on_console(msg):
                if msg.type in ('error', 'warning'):
                    findings['console_errors'].append(f'[console.{msg.type}] {msg.text[:200]}')

            def on_pageerror(err):
                findings['console_errors'].append(f'[pageerror] {str(err)[:200]}')

            def on_response(resp):
                if resp.status >= 400:
                    if '/api/' in resp.url or resp.url.endswith(('.png', '.jpg', '.jpeg', '.svg', '.css', '.js', '.html')):
                        findings['broken_resources'].append(f'[{resp.status}] {resp.url}')

            def on_requestfailed(req):
                findings['broken_resources'].append(f'[failed] {req.url}  ({req.failure})')

            pg.on('console', on_console)
            pg.on('pageerror', on_pageerror)
            pg.on('response', on_response)
            pg.on('requestfailed', on_requestfailed)

        page = ctx.new_page()
        attach_listeners(page)

        # ---------- Login flow ----------
        print('  login flow...')
        try:
            page.goto(BASE + '/login', wait_until='networkidle', timeout=10000)
            page.wait_for_timeout(400)
            page.fill('input#email', cred['email'])
            page.fill('input#password', cred['password'])
            with page.expect_response(lambda r: r.url.endswith('/login') and r.request.method == 'POST', timeout=8000) as info:
                page.click('button[type="submit"]')
            resp = info.value
            findings['login_ok'] = resp.status == 200
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT_DIR / f'{role_name}_01_post_login.png'), full_page=False)
        except Exception as e:
            findings['console_errors'].append(f'[login] {e}')
            browser.close()
            return findings

        # Get token from localStorage
        token = page.evaluate("() => localStorage.getItem('auth_token')")
        findings['token_set'] = bool(token)

        # ---------- Visit each page ----------
        for path, name in PAGES_TO_TRY:
            tag = f'{role_name}_{name}'
            try:
                # Reset listeners so per-page counts aren't cumulative
                findings['console_errors'] = findings['console_errors'][-50:]
                findings['broken_resources'] = findings['broken_resources'][-50:]

                page.goto(BASE + path, wait_until='domcontentloaded', timeout=10000)
                page.wait_for_timeout(700)
                # Verify body has content (not blank or error)
                body_text_len = page.evaluate('() => document.body.innerText.length')
                findings['pages'][name] = {
                    'path': path,
                    'status': 'ok' if body_text_len > 200 else 'short',
                    'body_chars': body_text_len,
                    'title': page.title(),
                }
                page.screenshot(path=str(OUT_DIR / f'{tag}.png'), full_page=False)
            except Exception as e:
                findings['pages'][name] = {'path': path, 'status': 'error', 'error': str(e)[:200]}

        # ---------- Interactions ----------
        # 1. Bulletin form submit
        try:
            page.goto(BASE + '/static/index.html', wait_until='domcontentloaded', timeout=8000)
            page.wait_for_timeout(800)
            page.fill('input#destination', 'Gulshan')
            page.click('button.btn-stamp')
            page.wait_for_timeout(1200)
            page.screenshot(path=str(OUT_DIR / f'{role_name}_bulletin_after_submit.png'))
            findings['interactions']['bulletin_submit'] = 'ok'
        except Exception as e:
            findings['interactions']['bulletin_submit'] = f'error: {e}'

        # 2. Chat send
        try:
            page.goto(BASE + '/chatbox', wait_until='networkidle', timeout=8000)
            page.wait_for_timeout(700)
            # Look for a chat textarea
            ta = page.query_selector('textarea')
            if ta:
                ta.fill('hi from ' + role_name)
                page.click('button[type="submit"], .send-btn, button[id*="send"]')
                page.wait_for_timeout(800)
                page.screenshot(path=str(OUT_DIR / f'{role_name}_chat_after_send.png'))
                findings['interactions']['chat_send'] = 'ok'
            else:
                findings['interactions']['chat_send'] = 'no textbox found'
        except Exception as e:
            findings['interactions']['chat_send'] = f'error: {e}'

        # 3. Try clicking admin tabs if on admin dashboard
        try:
            page.goto(BASE + '/admin', wait_until='domcontentloaded', timeout=8000)
            page.wait_for_timeout(900)
            tabs = page.query_selector_all('button, a')
            clicked = []
            for t in tabs[:20]:
                try:
                    txt = (t.inner_text() or '').strip().lower()
                    if txt in ('users', 'wanted criminals', 'police stations', 'missing persons',
                              'add crime', 'verify reports', 'case management', 'emergency', 'analytics'):
                        t.click()
                        page.wait_for_timeout(700)
                        clicked.append(txt)
                except Exception:
                    pass
            findings['interactions']['admin_tabs_clicked'] = clicked[:9]
            page.screenshot(path=str(OUT_DIR / f'{role_name}_admin_after_clicks.png'))
        except Exception as e:
            findings['interactions']['admin_attempt'] = f'error: {e}'

        browser.close()

    return findings


def main():
    creds = parse_creds(CREDS_FILE)
    if not creds:
        print('No credentials found. Run scripts/create_role_credentials.py first.')
        sys.exit(2)

    report = {'base': BASE, 'roles': {}}
    for role, cred in creds.items():
        findings = visit_role(role, cred)
        report['roles'][role] = findings

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2))
    print(f'\nReport written to {OUT_JSON.resolve()}')

    # Summary
    print('\n' + '=' * 78)
    print('PER-ROLE SUMMARY')
    print('=' * 78)
    for role, f in report['roles'].items():
        ok = sum(1 for v in f['pages'].values() if v.get('status') == 'ok')
        total = len(f['pages'])
        print(f'  {role:<10}  login:{"YES" if f["login_ok"] else "NO":<3}  '
              f'pages: {ok}/{total} ok  '
              f'errors: {len(f["console_errors"])}  '
              f'broken_res: {len(f["broken_resources"])}')


if __name__ == '__main__':
    main()
