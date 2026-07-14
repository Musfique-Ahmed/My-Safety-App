"""Unit tests for db.parse_json_field — used to coerce MySQL TEXT/JSON columns
back to Python dicts/lists across the codebase."""
from __future__ import annotations

import pytest

from db import parse_json_field


class TestParseJsonField:
    def test_none_returns_none(self):
        assert parse_json_field(None) is None

    def test_passthrough_dict(self):
        d = {"a": 1, "b": [2, 3]}
        assert parse_json_field(d) is d  # identity, not copy

    def test_passthrough_list(self):
        lst = [1, 2, 3]
        assert parse_json_field(lst) is lst

    def test_parses_json_string_dict(self):
        assert parse_json_field('{"k": "v"}') == {"k": "v"}

    def test_parses_json_string_list(self):
        assert parse_json_field("[1, 2, 3]") == [1, 2, 3]

    def test_parses_nested(self):
        s = '{"a": [1, {"b": true}], "c": null}'
        assert parse_json_field(s) == {"a": [1, {"b": True}], "c": None}

    def test_garbage_returns_none(self):
        assert parse_json_field("not json") is None
        assert parse_json_field("{unclosed") is None
        assert parse_json_field("[1, 2,") is None

    def test_empty_string_returns_none(self):
        assert parse_json_field("") is None

    def test_integer_returns_none(self):
        # numeric strings would actually parse in json.loads? No — int stays int.
        # parse_json_field only tries json.loads on non-dict/list input.
        assert parse_json_field(42) is None

    @pytest.mark.parametrize("v", [None, {}, [], {"x": 1}, [1], "", "abc"])
    def test_no_exception_on_any_input(self, v):
        # The whole point of this helper is to never raise.
        parse_json_field(v)