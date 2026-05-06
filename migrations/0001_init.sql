-- Canonical schema. Postgres-compatible DDL; SQLite is the current target.
-- BIGINT/INTEGER and TIMESTAMP work in both.

CREATE TABLE IF NOT EXISTS seasons (
    id              INTEGER PRIMARY KEY,
    masechet_slug   VARCHAR(64)  NOT NULL UNIQUE,
    masechet_name_en VARCHAR(128) NOT NULL,
    masechet_name_he VARCHAR(128) NOT NULL,
    season_number   INTEGER      NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS episodes (
    id                INTEGER PRIMARY KEY,
    season_id         INTEGER      NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    daf_number        INTEGER      NOT NULL,
    amud              VARCHAR(1),                    -- 'a', 'b', or NULL (full daf)
    daf_end           INTEGER,                       -- upper bound for combined-day recordings
    amud_end          VARCHAR(1),
    original_filename VARCHAR(512) NOT NULL,
    original_path     VARCHAR(2048) NOT NULL UNIQUE,
    file_size_bytes   BIGINT,
    recorded_at       TIMESTAMP,
    normalized_path   VARCHAR(2048),
    normalized_at     TIMESTAMP,
    duration_seconds  INTEGER,
    ia_identifier     VARCHAR(256),
    ia_url            VARCHAR(2048),
    ia_uploaded_at    TIMESTAMP,
    description       TEXT,
    title_en          VARCHAR(256) NOT NULL,
    title_he          VARCHAR(256) NOT NULL,
    CONSTRAINT uq_season_daf UNIQUE (season_id, daf_number)
);

CREATE INDEX IF NOT EXISTS idx_episodes_season       ON episodes (season_id);
CREATE INDEX IF NOT EXISTS idx_episodes_normalized   ON episodes (normalized_at);
CREATE INDEX IF NOT EXISTS idx_episodes_uploaded     ON episodes (ia_uploaded_at);

CREATE TABLE IF NOT EXISTS kv_state (
    key   VARCHAR(128) PRIMARY KEY,
    value TEXT
);
