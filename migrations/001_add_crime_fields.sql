-- Migration 001: Add reporter_id, incident_date, and evidence_files to crime table.
--
-- MySQL 8.x does NOT support `ADD COLUMN IF NOT EXISTS` (that's a MariaDB
-- extension). Instead, the migration runner catches "duplicate column"
-- errors (code 1060) and treats them as already-applied.
--
-- To re-run safely, just re-execute this file; duplicate-column errors are
-- expected on a DB where the columns already exist.

ALTER TABLE crime
  ADD COLUMN reporter_id VARCHAR(255) NULL AFTER crime_id,
  ADD COLUMN incident_date DATETIME NULL AFTER reporter_id,
  ADD COLUMN evidence_files LONGTEXT NULL AFTER witness_data;
