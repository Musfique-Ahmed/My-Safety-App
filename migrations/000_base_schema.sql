-- Migration 000: Base schema. Creates the four core tables that the
-- application code depends on. Migrations 001+ assume these exist.
--
-- Table names use the canonical names the application actually queries
-- against (appuser, crime.crime_id, etc.), per the schema-drift notes in
-- report.md Appendix A. Bringing up a fresh DB: run this first.

CREATE TABLE IF NOT EXISTS appuser (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(128),
  email VARCHAR(255) UNIQUE,
  password_hash VARCHAR(255),
  role_hint VARCHAR(50) DEFAULT 'user',
  status VARCHAR(32) DEFAULT 'active',
  full_name VARCHAR(255),
  phone VARCHAR(64),
  station_id INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL,
  last_login DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS uploads (
  upload_id INT AUTO_INCREMENT PRIMARY KEY,
  filename VARCHAR(512) NOT NULL,
  file_url VARCHAR(1024) NOT NULL,
  uploaded_by INT NULL,
  uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (uploaded_by) REFERENCES appuser(user_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS crime (
  crime_id INT AUTO_INCREMENT PRIMARY KEY,
  reporter_id VARCHAR(255) NULL,
  incident_date DATETIME NULL,
  location_data TEXT,
  crime_data TEXT,
  victim_data TEXT,
  criminal_data TEXT,
  weapon_data TEXT,
  witness_data TEXT,
  evidence_files LONGTEXT,
  status VARCHAR(64) NOT NULL DEFAULT 'Pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS missing_person (
  missing_id INT AUTO_INCREMENT PRIMARY KEY,
  name TEXT NOT NULL,
  nickname VARCHAR(255),
  hometown VARCHAR(255),
  age INT NULL,
  weight FLOAT NULL,
  hair_color VARCHAR(64),
  photo_url TEXT,
  last_seen_date DATETIME NULL,
  last_seen_location TEXT,
  description TEXT,
  medical_needs TEXT,
  reporter_name VARCHAR(255),
  reporter_phone VARCHAR(64),
  reporter_email VARCHAR(255),
  reporter_relation VARCHAR(128),
  status VARCHAR(64) DEFAULT 'Reported',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS wanted_criminal (
  criminal_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  alias VARCHAR(255),
  description TEXT,
  last_known_location TEXT,
  crimes TEXT,
  reward DECIMAL(12,2) DEFAULT 0,
  danger_level VARCHAR(64),
  photo_url TEXT,
  status VARCHAR(64) DEFAULT 'Active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
