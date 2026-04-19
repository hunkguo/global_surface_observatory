-- Global Surface Observatory (GSO) SQLite schema
-- 对应开发说明书 5.2 节

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS airports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    icao TEXT NOT NULL UNIQUE,
    iata TEXT,
    name TEXT,
    city TEXT,
    country TEXT,
    latitude REAL,
    longitude REAL,
    elevation_ft REAL,
    timezone TEXT,
    source TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_airports_iata    ON airports(iata);
CREATE INDEX IF NOT EXISTS idx_airports_country ON airports(country);

CREATE TABLE IF NOT EXISTS weather_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    base_url TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    total_stations INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS metar_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_run_id INTEGER REFERENCES fetch_runs(id),
    icao TEXT NOT NULL,
    source_code TEXT NOT NULL,
    observation_time TEXT,
    raw_text TEXT NOT NULL,
    sanitized_text TEXT,
    temperature_c REAL,
    dewpoint_c REAL,
    wind_dir INTEGER,
    wind_speed REAL,
    gust REAL,
    visibility TEXT,
    altimeter REAL,
    sea_level_pressure_mb REAL,
    flight_category TEXT,
    metar_type TEXT,
    raw_json TEXT,
    inserted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(icao, source_code, observation_time, raw_text)
);

CREATE INDEX IF NOT EXISTS idx_metar_icao_time ON metar_reports(icao, observation_time DESC);
CREATE INDEX IF NOT EXISTS idx_metar_run       ON metar_reports(fetch_run_id);

CREATE TABLE IF NOT EXISTS taf_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fetch_run_id INTEGER REFERENCES fetch_runs(id),
    icao TEXT NOT NULL,
    source_code TEXT NOT NULL,
    issue_time TEXT,
    valid_from TEXT,
    valid_to TEXT,
    raw_text TEXT NOT NULL,
    raw_json TEXT,
    inserted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(icao, source_code, issue_time, raw_text)
);

CREATE INDEX IF NOT EXISTS idx_taf_icao_time ON taf_reports(icao, issue_time DESC);
CREATE INDEX IF NOT EXISTS idx_taf_run       ON taf_reports(fetch_run_id);

CREATE TABLE IF NOT EXISTS forecast_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    taf_report_id INTEGER NOT NULL REFERENCES taf_reports(id) ON DELETE CASCADE,
    change_type TEXT,
    time_from TEXT,
    time_to TEXT,
    wind_dir INTEGER,
    wind_speed REAL,
    gust REAL,
    visibility TEXT,
    weather_text TEXT,
    cloud_json TEXT,
    temp_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_forecast_segments_taf ON forecast_segments(taf_report_id);

-- HTTP 缓存条件 GET 的状态，用于 metars/tafs cache.csv.gz 的 ETag / Last-Modified 短路
CREATE TABLE IF NOT EXISTS http_cache_state (
    url TEXT PRIMARY KEY,
    etag TEXT,
    last_modified TEXT,
    last_fetched_at TEXT,
    last_status INTEGER
);
