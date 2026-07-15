"""SQLAlchemy engine used by FastAPI handlers.

`engine` is imported throughout `app.main` (and any future routers) for direct
SQL execution via `text()`. Connection URL is built from environment variables;
defaults match the local MariaDB 12.3 install on port 3306.

Env vars:
    DB_USER (default root)
    DB_PASSWORD (default empty)
    DB_HOST (default localhost)
    DB_PORT (default 3306)
    DB_NAME (default mysafetydb)
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine


def _build_sqlalchemy_url() -> str:
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "mysafetydb")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


SQLALCHEMY_DATABASE_URL = _build_sqlalchemy_url()
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"charset": "utf8mb4"})
