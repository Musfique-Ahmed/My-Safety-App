-- Migration 004: Indexes on filter/sort columns.
-- Uses CREATE INDEX IF NOT EXISTS where supported; otherwise wrap in a
-- procedure-based existence check (see 004_indexes_fallback.sql for MySQL <8).

-- crime
CREATE INDEX IF NOT EXISTS idx_crime_status ON crime (status);
CREATE INDEX IF NOT EXISTS idx_crime_created_at ON crime (created_at);
CREATE INDEX IF NOT EXISTS idx_crime_reporter_id ON crime (reporter_id);

-- missing_person
CREATE INDEX IF NOT EXISTS idx_missing_person_status ON missing_person (status);
CREATE INDEX IF NOT EXISTS idx_missing_person_created_at ON missing_person (created_at);

-- wanted_criminal
CREATE INDEX IF NOT EXISTS idx_wanted_criminal_status ON wanted_criminal (status);
CREATE INDEX IF NOT EXISTS idx_wanted_criminal_created_at ON wanted_criminal (created_at);

-- appuser (filter by role/status; email already unique in many installs)
CREATE INDEX IF NOT EXISTS idx_appuser_role_hint ON appuser (role_hint);
CREATE INDEX IF NOT EXISTS idx_appuser_status ON appuser (status);

-- (Indexes for the tables created in 002 are inline in 002_missing_tables.sql:
--  chat_messages(user_id,created_at), criminal_sightings(criminal_id,last_seen_time),
--  case_assignments(crime_id) UNIQUE + (user_id), user_complaints(status,created_at).)