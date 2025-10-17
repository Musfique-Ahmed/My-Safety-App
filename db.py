import os
import json
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value is not None else default


DB_CONFIG = {
    "host": _get_env("DB_HOST", "127.0.0.1"),
    "port": int(_get_env("DB_PORT", "3306")),
    "user": _get_env("DB_USER", "root"),
    "password": _get_env("DB_PASSWORD", ""),
    "database": _get_env("DB_NAME", "mysafetydb"),
    "charset": "utf8mb4",
    "cursorclass": DictCursor,
    "autocommit": True,
}


@contextmanager
def get_conn():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()


def fetch_all(sql: str, params: tuple | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()


def fetch_one(sql: str, params: tuple | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def execute(sql: str, params: tuple | None = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount


def insert_and_get_id(sql: str, params: tuple | None = None) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.lastrowid


def parse_json_field(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


