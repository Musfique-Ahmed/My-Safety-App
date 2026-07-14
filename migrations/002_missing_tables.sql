-- Migration 002: Create the tables referenced by code that have no CREATE TABLE anywhere.
-- Run after 001_add_crime_fields.sql.
-- All IF NOT EXISTS; re-runnable.

-- status_history (was lazy-created in main.py:1473 via ensure_status_history_table)
CREATE TABLE IF NOT EXISTS status_history (
    history_id    INT AUTO_INCREMENT PRIMARY KEY,
    crime_id      INT NOT NULL,
    new_status    VARCHAR(100) NOT NULL,
    notes         TEXT NULL,
    changed_by    INT NULL,
    changed_at    DATETIME NOT NULL,
    INDEX idx_status_history_crime (crime_id),
    INDEX idx_status_history_changed (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- emergency_alerts (was lazy-created in main.py:1490)
CREATE TABLE IF NOT EXISTS emergency_alerts (
    alert_id                    INT AUTO_INCREMENT PRIMARY KEY,
    user_id                     INT NULL,
    user_snapshot               LONGTEXT NULL,
    linked_crime_id             INT NULL,
    location_label              VARCHAR(255) NULL,
    latitude                    DECIMAL(10, 7) NULL,
    longitude                   DECIMAL(10, 7) NULL,
    alert_type                  VARCHAR(100) NOT NULL,
    severity                    VARCHAR(50) NOT NULL DEFAULT 'High',
    description                 TEXT NULL,
    metadata                    LONGTEXT NULL,
    status                      VARCHAR(50) NOT NULL DEFAULT 'New',
    assigned_officer_id         INT NULL,
    assigned_officer_snapshot   LONGTEXT NULL,
    assigned_at                 DATETIME NULL,
    created_at                  DATETIME NOT NULL,
    resolved_at                 DATETIME NULL,
    INDEX idx_emergency_status (status),
    INDEX idx_emergency_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- police_station (referenced by /api/admin/police-stations)
CREATE TABLE IF NOT EXISTS police_station (
    station_id          INT AUTO_INCREMENT PRIMARY KEY,
    station_name        VARCHAR(120) NOT NULL,
    station_code        VARCHAR(40) NOT NULL,
    address             VARCHAR(255) NULL,
    phone               VARCHAR(40) NULL,
    email               VARCHAR(120) NULL,
    latitude            DECIMAL(10, 7) NULL,
    longitude           DECIMAL(10, 7) NULL,
    jurisdiction_area   VARCHAR(255) NULL,
    officer_in_charge   VARCHAR(120) NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_police_station_code (station_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- chat_messages (referenced by /api/chat/* and admin/chat-messages)
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NULL,
    message         TEXT NOT NULL,
    report_id       VARCHAR(64) NULL,
    is_admin        TINYINT(1) NOT NULL DEFAULT 0,
    read_by_admin   TINYINT(1) NOT NULL DEFAULT 0,
    read_by_user    TINYINT(1) NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_chat_messages_user (user_id, created_at),
    INDEX idx_chat_messages_report (report_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- criminal_sightings (referenced by /api/wanted-criminals/{id}/sighting and DELETE cascade)
CREATE TABLE IF NOT EXISTS criminal_sightings (
    sighting_id          INT AUTO_INCREMENT PRIMARY KEY,
    criminal_id          INT NOT NULL,
    last_seen_time       DATETIME NULL,
    last_seen_location   VARCHAR(255) NULL,
    still_with_finder    TINYINT(1) NOT NULL DEFAULT 0,
    reporter_contact     VARCHAR(120) NULL,
    verified             TINYINT(1) NOT NULL DEFAULT 0,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_criminal_sightings_criminal (criminal_id),
    INDEX idx_criminal_sightings_time (last_seen_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- case_assignments (referenced by /api/admin/assign-case, DELETE crime cascade, /case_assignments/)
CREATE TABLE IF NOT EXISTS case_assignments (
    assignment_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id          INT NOT NULL,
    crime_id         INT NOT NULL,
    duty_role        VARCHAR(64) NULL,
    assigned_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status           VARCHAR(40) NOT NULL DEFAULT 'Active',
    notes            TEXT NULL,
    completion_date  DATETIME NULL,
    UNIQUE KEY uq_case_assignments_crime (crime_id),
    INDEX idx_case_assignments_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- user_complaints (referenced by /api/admin/complaints/*)
CREATE TABLE IF NOT EXISTS user_complaints (
    complaint_id          INT AUTO_INCREMENT PRIMARY KEY,
    reporter_contact      VARCHAR(120) NULL,
    channel               VARCHAR(40) NULL,
    status                VARCHAR(40) NOT NULL DEFAULT 'Pending',
    priority              VARCHAR(20) NULL,
    assigned_to           INT NULL,
    verification_notes    TEXT NULL,
    complaint_data        LONGTEXT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME NULL,
    INDEX idx_user_complaints_status (status),
    INDEX idx_user_complaints_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;