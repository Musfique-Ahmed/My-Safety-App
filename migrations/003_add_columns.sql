-- Migration 003: Add columns that code references but documented schema lacks.
--
-- NOTE: This file uses bare `ADD COLUMN` (not `IF NOT EXISTS`) because that
-- extension is MariaDB-only; MySQL 8.x lacks it. The migration runner
-- catches "duplicate column" (1060) errors and treats them as already
-- applied, so this file is idempotent.

-- crime
ALTER TABLE crime ADD COLUMN witness_info TEXT NULL AFTER witness_data;
ALTER TABLE crime ADD COLUMN priority_level VARCHAR(32) NOT NULL DEFAULT 'normal' AFTER status;
ALTER TABLE crime ADD COLUMN updated_at DATETIME NULL AFTER created_at;

-- wanted_criminal
ALTER TABLE wanted_criminal ADD COLUMN age_range VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN gender VARCHAR(20) NULL;
ALTER TABLE wanted_criminal ADD COLUMN height VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN weight VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN hair_color VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN eye_color VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN distinguishing_marks TEXT NULL;
ALTER TABLE wanted_criminal ADD COLUMN wanted_since DATE NULL;
ALTER TABLE wanted_criminal ADD COLUMN added_by INT NULL;
ALTER TABLE wanted_criminal ADD COLUMN crimes_committed TEXT NULL;
ALTER TABLE wanted_criminal ADD COLUMN reward_amount DECIMAL(12, 2) NULL DEFAULT 0;
ALTER TABLE wanted_criminal ADD COLUMN last_seen_reported_at DATETIME NULL;
ALTER TABLE wanted_criminal ADD COLUMN last_seen_reported_location VARCHAR(255) NULL;
ALTER TABLE wanted_criminal ADD COLUMN last_seen_with_finder TINYINT(1) NULL DEFAULT 0;
ALTER TABLE wanted_criminal ADD COLUMN capture_date DATE NULL;
ALTER TABLE wanted_criminal ADD COLUMN updated_at DATETIME NULL;

-- missing_person
ALTER TABLE missing_person ADD COLUMN reporter_id INT NULL;
ALTER TABLE missing_person ADD COLUMN gender VARCHAR(20) NULL;
ALTER TABLE missing_person ADD COLUMN last_seen_time DATETIME NULL;
ALTER TABLE missing_person ADD COLUMN height VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN eye_color VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN distinguishing_marks TEXT NULL;
ALTER TABLE missing_person ADD COLUMN clothing_description TEXT NULL;
ALTER TABLE missing_person ADD COLUMN contact_person VARCHAR(120) NULL;
ALTER TABLE missing_person ADD COLUMN contact_phone VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN police_case_number VARCHAR(80) NULL;
ALTER TABLE missing_person ADD COLUMN finding_location VARCHAR(255) NULL;
ALTER TABLE missing_person ADD COLUMN finder_name VARCHAR(120) NULL;
ALTER TABLE missing_person ADD COLUMN finder_phone VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN finder_email VARCHAR(120) NULL;
ALTER TABLE missing_person ADD COLUMN still_with_finder TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE missing_person ADD COLUMN updated_at DATETIME NULL;
