"""Backward-compat shim. The real module is `app.db`."""
from app.db import (  # noqa: F401
    fetch_one,
    fetch_all,
    execute,
    insert_and_get_id,
    parse_json_field,
    get_conn,
)