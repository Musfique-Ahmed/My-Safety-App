-- Migration: Add reporter_id, incident_date, and evidence_files to crime table
-- Run this against the `mysafetydb` database to make schema consistent with application.

ALTER TABLE crime
ADD COLUMN IF NOT EXISTS reporter_id VARCHAR(255) NULL AFTER crime_id,
ADD COLUMN IF NOT EXISTS incident_date DATETIME NULL AFTER reporter_id,
ADD COLUMN IF NOT EXISTS evidence_files LONGTEXT NULL AFTER witness_data;

-- evidence_files will store JSON array of {filename, url} objects
