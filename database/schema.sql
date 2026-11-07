-- VIGILENS database schema. Executed on every start; every statement is
-- idempotent (IF NOT EXISTS) so the database is created automatically the
-- first time the application runs and left untouched afterwards.

CREATE TABLE IF NOT EXISTS sessions (
    session_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time              TEXT    NOT NULL,            -- ISO 8601, local time
    end_time                TEXT,                        -- NULL while monitoring
    duration                REAL    NOT NULL DEFAULT 0,  -- seconds
    total_drowsiness_alerts INTEGER NOT NULL DEFAULT 0,
    total_yawning_events    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS detection_events (
    event_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id           INTEGER NOT NULL
                         REFERENCES sessions(session_id) ON DELETE CASCADE,
    event_type           TEXT    NOT NULL
                         CHECK (event_type IN ('DROWSINESS_ALERT', 'YAWNING')),
    timestamp            TEXT    NOT NULL,
    ear_value            REAL,
    mar_value            REAL,
    eye_closure_duration REAL    NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_session ON detection_events(session_id);

-- Smoothed EAR sampled a couple of times per second; powers the
-- "EAR over time" chart in Analytics.
CREATE TABLE IF NOT EXISTS ear_samples (
    sample_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL
                    REFERENCES sessions(session_id) ON DELETE CASCADE,
    elapsed_seconds REAL    NOT NULL,
    ear_value       REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_session ON ear_samples(session_id);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
