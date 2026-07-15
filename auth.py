"""Backward-compat shim. The real module is `app.core.security`."""
from app.core.security import (  # noqa: F401
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    get_current_user,
    require_user,
    require_admin,
)
# Old `auth.py` re-exported `db.fetch_one` too (it did `from db import
# fetch_one`); keep the name available so legacy monkeypatches still find it.
from app.db import fetch_one  # noqa: F401
# Constants that used to live at module scope in legacy `auth.py` — keep
# them as aliases so tests that monkeypatch `auth.JWT_EXPIRES_MINUTES` etc.
# still find the name.
from app.core.config import (  # noqa: F401
    JWT_ALGORITHM,
    JWT_EXPIRES_MINUTES,
    JWT_SECRET,
)