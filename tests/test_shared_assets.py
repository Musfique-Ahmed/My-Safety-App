"""Smoke tests for the shared frontend JS helpers (api-base.js, escape.js,
header.js). Run them through Node with a minimal window/document/localStorage
polyfill so we can assert the documented globals exist and behave correctly.

Browser-side scripts attach to `window.x` — so we read global.window.x here.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "static" / "assets" / "js"


POLYFILL = (
    "global.window = global.window || {};\n"
    "global.window.location = global.window.location || { origin: 'http://test.local' };\n"
    "global.document = global.document || {\n"
    "  getElementById: () => null,\n"
    "  querySelector: () => null,\n"
    "  querySelectorAll: () => [],\n"
    "  addEventListener: () => {},\n"
    "  createElement: () => ({ setAttribute: () => {}, appendChild: () => {} }),\n"
    "  body: { appendChild: () => {} },\n"
    "  head: { appendChild: () => {} },\n"
    "  location: global.window.location,\n"
    "};\n"
    "global.localStorage = global.localStorage || {\n"
    "  _s: {},\n"
    "  getItem(k){return this._s[k] ?? null;},\n"
    "  setItem(k,v){this._s[k]=v;},\n"
    "  removeItem(k){delete this._s[k];},\n"
    "};\n"
    "global.fetch = global.fetch || (() => Promise.resolve({ok:true,json:()=>Promise.resolve({})}));\n"
)


def _run_node(script: str) -> dict:
    """Execute a small JS snippet via node and return parsed JSON output."""
    p = subprocess.run(
        ["node", "-e", POLYFILL + script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    if p.returncode != 0:
        raise AssertionError(f"node -e failed:\nSTDERR: {p.stderr}\nSTDOUT: {p.stdout}")
    try:
        return json.loads(p.stdout.strip())
    except json.JSONDecodeError:
        return {"raw": p.stdout}


def _load(path: Path) -> str:
    return f"require('{path.as_posix()}');\n"


class TestApiBaseJs:
    def test_file_exists(self):
        assert (ASSETS_DIR / "api-base.js").is_file()

    def test_exposes_api_base_and_resolver(self):
        result = _run_node(
            _load(ASSETS_DIR / "api-base.js")
            + "process.stdout.write(JSON.stringify({"
            "apiBase: typeof global.window.API_BASE,"
            "resolve: typeof global.window.resolveApiUrl"
            "}));"
        )
        assert result["apiBase"] == "string"
        assert result["resolve"] == "function"

    def test_resolver_returns_origin_plus_path(self):
        result = _run_node(
            _load(ASSETS_DIR / "api-base.js")
            + "process.stdout.write(JSON.stringify({"
            "got: global.window.resolveApiUrl('/api/x')"
            "}));"
        )
        assert result["got"] == "http://test.local/api/x"


class TestEscapeJs:
    def test_file_exists(self):
        assert (ASSETS_DIR / "escape.js").is_file()

    def test_exposes_escape_html(self):
        result = _run_node(
            _load(ASSETS_DIR / "escape.js")
            + "process.stdout.write(JSON.stringify({"
            "has: typeof global.window.escapeHtml,"
            "result: global.window.escapeHtml('<script>alert(1)</script>')"
            "}));"
        )
        assert result["has"] == "function"
        assert "<script>" not in result["result"]
        assert "&lt;script&gt;" in result["result"]

    def test_escapes_all_owasp_chars(self):
        result = _run_node(
            _load(ASSETS_DIR / "escape.js")
            + "process.stdout.write(JSON.stringify({"
            "s: global.window.escapeHtml('&<>\"\\'/')"
            "}));"
        )
        s = result["s"]
        assert "&amp;" in s
        assert "&lt;" in s
        assert "&gt;" in s
        assert "&quot;" in s or "&#34;" in s


class TestHeaderJs:
    def test_file_exists(self):
        assert (ASSETS_DIR / "header.js").is_file()