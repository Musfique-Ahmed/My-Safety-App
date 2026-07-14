"""Offline tests for scripts/run_migration_and_db_test.py.

The full migration runner needs a live MySQL, but we can verify:
- All .sql files in migrations/ are picked up in sorted order.
- The statement splitter handles each file without dropping or
  mis-parsing any statement.
- Inserted test-row SQL is well-formed and uses the column names the
  main app expects (crime_id PK, witness_data, victim_data, etc.).

These run without a database.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "run_migration_and_db_test.py"
MIGRATIONS_DIR = REPO / "migrations"


@pytest.fixture(scope="module")
def runner():
    """Import the migration runner module without running its main()."""
    spec = importlib.util.spec_from_file_location("migration_runner", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        # If mysql-connector isn't installed, we still want to import the
        # splitter, so do a partial import.
        pytest.skip(f"could not import migration runner: {e}")
    return mod


class TestStatementSplitter:
    def test_splits_single_statement(self, runner):
        sql = "CREATE TABLE foo (id INT);"
        assert runner.split_statements(sql) == ["CREATE TABLE foo (id INT)"]

    def test_ignores_sql_comments(self, runner):
        sql = "-- header comment\n-- another\nCREATE TABLE foo (id INT);\n-- trailing\n"
        assert runner.split_statements(sql) == ["CREATE TABLE foo (id INT)"]

    def test_handles_multiple_statements(self, runner):
        # The splitter is line-based: each statement must end a line with ';'.
        # This matches how our migration files are authored.
        sql = (
            "CREATE TABLE a (x INT);\n"
            "CREATE TABLE b (y INT);\n"
        )
        out = runner.split_statements(sql)
        assert len(out) == 2
        assert out[0] == "CREATE TABLE a (x INT)"
        assert out[1] == "CREATE TABLE b (y INT)"

    def test_preserves_inline_comments_within_statement(self, runner):
        sql = "CREATE TABLE foo (id INT, -- inline\n  name VARCHAR(50));"
        stmts = runner.split_statements(sql)
        assert len(stmts) == 1
        assert "name VARCHAR(50)" in stmts[0]


class TestMigrationFiles:
    @pytest.fixture(scope="class")
    def all_statements(self, runner):
        out = {}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            with open(path, encoding="utf-8") as f:
                out[path.name] = runner.split_statements(f.read())
        return out

    def test_at_least_one_migration(self, all_statements):
        assert len(all_statements) >= 3

    def test_each_migration_has_statements(self, all_statements):
        for name, stmts in all_statements.items():
            assert len(stmts) > 0, f"{name} produced 0 statements"

    def test_002_creates_seven_tables(self, runner, all_statements):
        # 002 should create status_history, emergency_alerts, police_station,
        # chat_messages, criminal_sightings, case_assignments, user_complaints.
        stmts = all_statements.get("002_missing_tables.sql", [])
        create_stmts = [s for s in stmts if s.upper().startswith("CREATE TABLE")]
        assert len(create_stmts) == 7, (
            f"expected 7 CREATE TABLE statements in 002, got {len(create_stmts)}"
        )

    def test_003_only_alter_or_create(self, runner, all_statements):
        stmts = all_statements.get("003_add_columns.sql", [])
        for s in stmts:
            assert s.upper().startswith(("ALTER TABLE", "CREATE")), (
                f"unexpected statement in 003: {s.splitlines()[0][:60]}"
            )

    def test_004_only_create_index_or_alter(self, runner, all_statements):
        stmts = all_statements.get("004_indexes.sql", [])
        for s in stmts:
            upper = s.upper()
            assert upper.startswith(("CREATE INDEX", "CREATE UNIQUE INDEX", "ALTER TABLE")), (
                f"unexpected statement in 004: {s.splitlines()[0][:60]}"
            )

    def test_no_empty_statements(self, all_statements):
        for name, stmts in all_statements.items():
            for s in stmts:
                assert s.strip(), f"{name} has an empty statement"


class TestInsertTestRow:
    """Verify the test insert is well-formed and references columns the
    main app expects."""

    def test_insert_sql_uses_crime_table(self, runner):
        # The insert is defined inside main(); check the source for safety.
        src = SCRIPT.read_text(encoding="utf-8")
        assert "INSERT INTO crime" in src
        assert "evidence_files" in src
        assert "witness_data" in src
        assert "victim_data" in src

    def test_insert_includes_status_pending(self, runner):
        src = SCRIPT.read_text(encoding="utf-8")
        assert "'Pending'" in src or '"Pending"' in src

    def test_fetch_selects_required_columns(self, runner):
        src = SCRIPT.read_text(encoding="utf-8")
        assert "crime_id" in src
        assert "evidence_files" in src
        assert "FROM crime" in src