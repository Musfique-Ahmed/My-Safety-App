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

    def test_all_migrations_present(self):
        for fname in (
            "000_base_schema.sql",
            "001_add_crime_fields.sql",
            "002_missing_tables.sql",
            "003_add_columns.sql",
            "004_indexes.sql",
            "005_admin_tables.sql",
        ):
            f = MIGRATIONS_DIR / fname
            assert f.is_file(), f"missing {fname}"
            assert f.stat().st_size > 0, f"{fname} is empty"


class TestMigrationsContent:
    @pytest.mark.parametrize(
        "fname,required_substrings",
        [
            (
                "000_base_schema.sql",
                ["appuser", "crime", "missing_person", "wanted_criminal"],
            ),
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
            (
                "005_admin_tables.sql",
                ["evidence_files", "file_uploads", "activity_log",
                 "admin_activity_log", "complaints", "notifications"],
            ),
        ],
    )
    def test_migration_has_expected_statements(self, fname, required_substrings):
        text = (MIGRATIONS_DIR / fname).read_text(encoding="utf-8")
        for needle in required_substrings:
            assert needle in text, f"{fname} should contain {needle!r}"


class TestMigrationsMySQLCompatible:
    """Verify migrations don't use MariaDB-only syntax that MySQL 8.x rejects.

    Strips SQL comments first so explanatory text (e.g. "MySQL 8.x does NOT
    support ADD COLUMN IF NOT EXISTS") doesn't trigger a false positive.
    """

    @staticmethod
    def _strip_comments(text: str) -> str:
        # Remove lines starting with --, then uppercase
        lines = []
        for ln in text.splitlines():
            stripped = ln.strip()
            if stripped.startswith("--"):
                continue
            lines.append(ln)
        return "\n".join(lines).upper()

    @pytest.mark.parametrize("fname", [
        "000_base_schema.sql",
        "001_add_crime_fields.sql",
        "003_add_columns.sql",
        "004_indexes.sql",
        "005_admin_tables.sql",
    ])
    def test_no_add_column_if_not_exists(self, fname):
        text = self._strip_comments((MIGRATIONS_DIR / fname).read_text(encoding="utf-8"))
        assert "ADD COLUMN IF NOT EXISTS" not in text, (
            f"{fname} uses MariaDB-only 'ADD COLUMN IF NOT EXISTS'; "
            "MySQL 8.x rejects this with syntax error 1064."
        )

    @pytest.mark.parametrize("fname", ["004_indexes.sql"])
    def test_no_create_index_if_not_exists(self, fname):
        text = self._strip_comments((MIGRATIONS_DIR / fname).read_text(encoding="utf-8"))
        assert "CREATE INDEX IF NOT EXISTS" not in text, (
            f"{fname} uses MariaDB-only 'CREATE INDEX IF NOT EXISTS'."
        )


class TestMigrationOrdering:
    def test_migration_files_sort_in_order(self):
        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for f in files:
            stem = f.stem
            prefix = stem.split("_", 1)[0]
            assert prefix.isdigit(), f"{f.name} should start with a numeric prefix"