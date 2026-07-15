"""Unit tests for auth.hash_password / verify_password / create_access_token /
decode_token. No DB or FastAPI needed."""
from __future__ import annotations

import time

import pytest

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)


class TestPasswordHashing:
    def test_hash_returns_bcrypt_string(self):
        h = hash_password("hunter2")
        assert isinstance(h, str)
        assert h.startswith("$2")  # bcrypt prefix
        assert h != "hunter2"  # not plaintext

    def test_hash_different_for_same_input(self):
        # bcrypt uses a random salt
        assert hash_password("hunter2") != hash_password("hunter2")

    def test_verify_accepts_correct_password(self):
        h = hash_password("correcthorsebatterystaple")
        assert verify_password("correcthorsebatterystaple", h) is True

    def test_verify_rejects_wrong_password(self):
        h = hash_password("correcthorsebatterystaple")
        assert verify_password("wrong", h) is False

    def test_verify_rejects_empty_hash(self):
        assert verify_password("anything", "") is False
        assert verify_password("anything", None) is False

    @pytest.mark.parametrize("bad", ["", None, 123, b"bytes-not-str"])
    def test_hash_rejects_invalid_password(self, bad):
        with pytest.raises((ValueError, TypeError)):
            hash_password(bad)


class TestTokens:
    def test_create_returns_string(self):
        tok = create_access_token(user_id=1)
        assert isinstance(tok, str)
        # JWTs have 3 dot-separated segments
        assert tok.count(".") == 2

    def test_decode_roundtrip(self):
        tok = create_access_token(user_id=42, role="admin")
        payload = decode_token(tok)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["role"] == "admin"

    def test_decode_returns_none_for_garbage(self):
        assert decode_token("not.a.jwt") is None
        assert decode_token("") is None
        assert decode_token("only-one-part") is None

    def test_decode_returns_none_for_tampered_signature(self):
        tok = create_access_token(user_id=1)
        tampered = tok[:-2] + ("AA" if tok[-2:] != "AA" else "BB")
        assert decode_token(tampered) is None

    def test_expired_token_returns_none(self, monkeypatch):
        # Force expiry to be in the past. The canonical constant lives in
        # app.core.config, but security.py bound its own copy via
        # `from app.core.config import JWT_EXPIRES_MINUTES`. Patch the
        # source AND the re-export so `create_access_token` actually
        # reads the patched value.
        import app.core.config as config_mod
        import app.core.security as security_mod
        import auth as auth_mod

        monkeypatch.setattr(config_mod, "JWT_EXPIRES_MINUTES", -1)
        monkeypatch.setattr(security_mod, "JWT_EXPIRES_MINUTES", -1)
        monkeypatch.setattr(auth_mod, "JWT_EXPIRES_MINUTES", -1)
        tok = security_mod.create_access_token(user_id=1)
        assert decode_token(tok) is None

    def test_role_optional(self):
        tok_no_role = create_access_token(user_id=1)
        tok_with_role = create_access_token(user_id=1, role="officer")
        assert decode_token(tok_no_role) is not None
        assert "role" not in decode_token(tok_no_role)
        assert decode_token(tok_with_role)["role"] == "officer"

    def test_iat_and_exp_set(self):
        tok = create_access_token(user_id=1)
        p = decode_token(tok)
        assert "iat" in p and "exp" in p
        assert p["exp"] > p["iat"]