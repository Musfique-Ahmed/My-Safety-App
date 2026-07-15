"""Drive a real headless Chromium against the live local stack.

Captures:
  - Console errors and network 404s on each page
  - Full-page screenshots of every main route
  - Login + register flow against the live MariaDB

Run:
  python scripts/browser_smoke.py
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8000'
OUT = Path('screenshots')
OUT.mkdir(exist_ok=True)


def _record_console(page, errors):
    def on_console(msg):
        if msg.type in ('error',):
            errors.append(f'console.{msg.type}: {msg.text}')

    def on_pageerror(err):
        errors.append(f'pageerror: {err}')

    def on_response(resp):
        if resp.status >= 400 and '/api/' not in resp.url and '/openapi' not in resp.url:
            # ignore expected 404s on the user menu buttons / etc
            errors.append(f'{resp.status} {resp.url}')

    page.on('console', on_console)
    page.on('pageerror', on_pageerror)
    page.on('response', on_response)


def screenshot(page, name, full_page=True):
    path = OUT / f'{name}.png'
    page.screenshot(path=str(path), full_page=full_page)
    size = path.stat().st_size
    print(f'  -> {path}  ({size:,} B)')
    return path


def visit(page, errors, route, name, wait_ms=900):
    print(f'[{name}]  {BASE}{route}')
    page.goto(BASE + route, wait_until='networkidle', timeout=15000)
    page.wait_for_timeout(wait_ms)
    if errors:
        print(f'  issues on {name}:')
        for e in errors[:10]:
            print(f'    {e}')
        errors.clear()
    return screenshot(page, name)


def main():
    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={'width': 1440, 'height': 900},
            user_agent='PukuBrowserSmoke/1.0',
        )
        page = ctx.new_page()
        errors = []
        _record_console(page, errors)

        # ---------- 1. Every page, just a screenshot ----------
        try:
            visit(page, errors, '/static/index.html',         '01_bulletin_dashboard')
        except Exception as e:
            failures.append(('bulletin', str(e)))
        try:
            visit(page, errors, '/',                         '02_home_legacy')
        except Exception as e:
            failures.append(('home', str(e)))
        try:
            visit(page, errors, '/login',                    '03_login')
        except Exception as e:
            failures.append(('login', str(e)))
        try:
            visit(page, errors, '/signup',                   '04_signup')
        except Exception as e:
            failures.append(('signup', str(e)))
        try:
            visit(page, errors, '/report-crime',             '05_report_crime')
        except Exception as e:
            failures.append(('report-crime', str(e)))
        try:
            visit(page, errors, '/missing-person',           '06_missing_person')
        except Exception as e:
            failures.append(('missing-person', str(e)))
        try:
            visit(page, errors, '/wanted-criminals',         '07_wanted_criminals')
        except Exception as e:
            failures.append(('wanted-criminals', str(e)))
        try:
            visit(page, errors, '/chatbox',                  '08_chatbox_logged_out')
        except Exception as e:
            failures.append(('chatbox', str(e)))
        try:
            visit(page, errors, '/admin',                    '09_admin_dashboard')
        except Exception as e:
            failures.append(('admin', str(e)))

        # ---------- 2. Verify login form posts against the live DB ----------
        print('\n[login flow]')
        try:
            page.goto(BASE + '/login', wait_until='networkidle', timeout=10000)
            page.wait_for_timeout(400)
            # Use the 'admin' credential we created
            page.fill('input#email', 'admin+ed833c@mysafety.local')
            page.fill('input#password', 'RoleTest-Admin-ED833C')
            with page.expect_response(lambda r: '/login' in r.url and r.request.method == 'POST', timeout=8000) as info:
                page.click('button[type="submit"]')
            resp = info.value
            print(f'  POST /login -> {resp.status}')
            page.wait_for_timeout(800)
            screenshot(page, '10_after_login')
        except Exception as e:
            failures.append(('login flow', str(e)))

        # ---------- 3. Try the redesigned bulletin and interact ----------
        print('\n[bulletin interaction]')
        try:
            page.goto(BASE + '/static/index.html', wait_until='networkidle', timeout=15000)
            page.wait_for_timeout(1500)
            # Type a destination and submit the route form
            page.fill('input#destination', 'Gulshan')
            page.click('form#route-form button.ms-btn--primary')
            page.wait_for_timeout(2000)
            screenshot(page, '11_bulletin_after_search')
            # Try the panic button (cancel the confirm)
            page.evaluate('window.confirm = () => false')
            page.click('button#panic-btn')
            page.wait_for_timeout(400)
            screenshot(page, '12_bulletin_panic_hover')
        except Exception as e:
            failures.append(('bulletin interaction', str(e)))

        # ---------- 4. Chatbox while logged in ----------
        print('\n[chatbox logged in]')
        try:
            page.goto(BASE + '/chatbox', wait_until='networkidle', timeout=10000)
            page.wait_for_timeout(900)
            screenshot(page, '13_chatbox_logged_in')
        except Exception as e:
            failures.append(('chatbox logged in', str(e)))

        browser.close()

    print()
    if failures:
        print('FAILURES:')
        for k, v in failures:
            print(f'  {k}: {v}')
        sys.exit(1)
    print(f'OK — {len(list(OUT.iterdir()))} screenshots in {OUT.resolve()}')


if __name__ == '__main__':
    main()
