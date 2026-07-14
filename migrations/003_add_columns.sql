-- Migration 003: Add columns that code references but documented schema lacks.
-- Uses ADD COLUMN IF NOT EXISTS (MySQL 8.0.29+). On older servers, run the
-- fallback 003_add_columns_fallback.sql instead.

-- crime
ALTER TABLE crime ADD COLUMN IF NOT EXISTS witness_info TEXT NULL AFTER witness_data;
ALTER TABLE crime ADD COLUMN IF NOT EXISTS priority_level VARCHAR(32) NOT NULL DEFAULT 'normal' AFTER status;
ALTER TABLE crime ADD COLUMN IF NOT EXISTS updated_at DATETIME NULL AFTER created_at;

-- wanted_criminal
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS age_range VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS gender VARCHAR(20) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS height VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS weight VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS hair_color VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS eye_color VARCHAR(40) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS distinguishing_marks TEXT NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS wanted_since DATE NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS added_by INT NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS crimes_committed TEXT NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS reward_amount DECIMAL(12, 2) NULL DEFAULT 0;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS last_seen_reported_at DATETIME NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS last_seen_reported_location VARCHAR(255) NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS last_seen_with_finder TINYINT(1) NULL DEFAULT 0;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS capture_date DATE NULL;
ALTER TABLE wanted_criminal ADD COLUMN IF NOT EXISTS updated_at DATETIME NULL;

-- missing_person
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS reporter_id INT NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS last_seen_time DATETIME NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS height VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS eye_color VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS distinguishing_marks TEXT NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS clothing_description TEXT NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS contact_person VARCHAR(120) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS police_case_number VARCHAR(80) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS finding_location VARCHAR(255) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS finder_name VARCHAR(120) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS finder_phone VARCHAR(40) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS finder_email VARCHAR(120) NULL;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS still_with_finder TINYINT(1) NOT NULL DEFAULT 0;
ALTER TABLE missing_person ADD COLUMN IF NOT EXISTS updated_at DATETIME NULL;