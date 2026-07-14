"""Smoke test for migrations/ — verify the SQL files exist and contain the
expected statements. Doesn't require a DB.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


class TestMigrationsExist:
    def test_migrations_dir_exists(self):
        assert MIGRATIONS_DIR.is_dir(), f"{MIGRATIONS_DIR} should exist"

    def test_002_through_004_present(self):
        for fname in ("002_missing_tables.sql", "003_add_columns.sql", "004_indexes.sql"):
            f = MIGRATIONS_DIR / fname
            assert f.is_file(), f"missing {fname}"
            assert f.stat().st_size > 0, f"{fname} is empty"


class TestMigrationsContent:
    @pytest.mark.parametrize(
        "fname,required_substrings",
        [
            (
                "002_missing_tables.sql",
                ["police_station", "chat_messages", "criminal_sightings",
                 "case_assignments", "user_complaints", "CREATE TABLE"],
            ),
            (
                "003_add_columns.sql",
                ["ALTER TABLE", "ADD COLUMN"],
            ),
            (
                "004_indexes.sql",
                ["CREATE INDEX"],
            ),
        ],
    )
    def test_migration_has_expected_statements(self, fname, required_substrings):
        text = (MIGRATIONS_DIR / fname).read_text(encoding="utf-8")
        for needle in required_substrings:
            assert needle in text, f"{fname} should contain {needle!r}"


class TestMigrationOrdering:
    def test_migration_files_sort_in_order(self):
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for f in files:
            stem = f.stem
            prefix = stem.split("_", 1)[0]
            assert prefix.isdigit(), f"{f.name} should start with a numeric prefix"