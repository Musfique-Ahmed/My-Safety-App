-- Migration 005: Additional tables referenced by main_admin.py that the
-- original schema + migrations 000-004 don't cover.
--
-- These tables are read by /admin-api/api/admin/* endpoints. Each is
-- created with IF NOT EXISTS so the file is re-runnable.

CREATE TABLE IF NOT EXISTS evidence_files (
    file_id INT AUTO_INCREMENT PRIMARY KEY,
    crime_id INT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    file_size BIGINT,
    uploaded_by INT NULL,
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS file_uploads (
    upload_id INT AUTO_INCREMENT PRIMARY KEY,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(100),
    file_size BIGINT,
    uploaded_by INT NULL,
    related_table VARCHAR(50),
    related_id INT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS activity_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    activity_type VARCHAR(100) NOT NULL,
    item_id INT NULL,
    details TEXT,
    performed_by INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS admin_activity_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    admin_id INT NULL,
    action_type VARCHAR(100) NOT NULL,
    target_table VARCHAR(100),
    target_id INT,
    action_details TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS api_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    method VARCHAR(10),
    path VARCHAR(512),
    status_code INT,
    user_id INT NULL,
    duration_ms INT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id INT AUTO_INCREMENT PRIMARY KEY,
    reporter_id INT NULL,
    reporter_contact VARCHAR(255),
    complaint_text TEXT,
    channel VARCHAR(64),
    status VARCHAR(64) DEFAULT 'pending',
    priority VARCHAR(32) DEFAULT 'normal',
    assigned_to INT NULL,
    verification_notes TEXT,
    complaint_data TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    title VARCHAR(255),
    body TEXT,
    is_read TINYINT(1) DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS system_settings (
    setting_key VARCHAR(128) PRIMARY KEY,
    setting_value TEXT,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS user_sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    ip_address VARCHAR(64),
    user_agent VARCHAR(512),
    login_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    logout_time DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS active_cases (
    case_id INT AUTO_INCREMENT PRIMARY KEY,
    crime_id INT NULL,
    assigned_to INT NULL,
    status VARCHAR(64) DEFAULT 'open',
    priority VARCHAR(32) DEFAULT 'normal',
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS officer_workload (
    user_id INT PRIMARY KEY,
    full_name VARCHAR(255),
    station_name VARCHAR(255),
    active_assignments INT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;