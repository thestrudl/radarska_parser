-- TimescaleDB schema for the radar parser service.
-- Mounted into the TimescaleDB container's docker-entrypoint-initdb.d so it runs
-- once on first start (empty data volume).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Named locations (registered via API). ---------------------------------------
CREATE TABLE IF NOT EXISTS locations (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(80) UNIQUE NOT NULL,
    address   VARCHAR(255),
    lat       DOUBLE PRECISION NOT NULL,
    lon       DOUBLE PRECISION NOT NULL,
    x         DOUBLE PRECISION NOT NULL,
    y         DOUBLE PRECISION NOT NULL,
    radius    DOUBLE PRECISION NOT NULL,
    radiuspx  DOUBLE PRECISION NOT NULL
);

-- Per-location precipitation time series. --------------------------------------
CREATE TABLE IF NOT EXISTS location_readings (
    time         TIMESTAMPTZ NOT NULL,
    location_id  INTEGER NOT NULL,
    mm_h         DOUBLE PRECISION NOT NULL,
    storm        BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (time, location_id)
);
SELECT create_hypertable('location_readings', 'time', if_not_exists => TRUE);

-- Coarse-grid precipitation (powers click-anywhere queries). -------------------
CREATE TABLE IF NOT EXISTS precip_grid (
    time    TIMESTAMPTZ NOT NULL,
    cell_x  INTEGER NOT NULL,
    cell_y  INTEGER NOT NULL,
    mm_h    DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, cell_x, cell_y)
);
SELECT create_hypertable('precip_grid', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_precip_grid_cell ON precip_grid (cell_x, cell_y, time DESC);

-- Full-resolution frame archive (ML training corpus). --------------------------
CREATE TABLE IF NOT EXISTS radar_frames (
    id            BIGSERIAL PRIMARY KEY,
    time          TIMESTAMPTZ NOT NULL,
    gif_path      TEXT NOT NULL,
    npy_path      TEXT NOT NULL,
    palette_hash  VARCHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_radar_frames_time ON radar_frames (time DESC);
CREATE INDEX IF NOT EXISTS idx_radar_frames_hash ON radar_frames (palette_hash);

-- Surface weather observations (future ML features). ---------------------------
CREATE TABLE IF NOT EXISTS weather_obs (
    time          TIMESTAMPTZ NOT NULL,
    station       VARCHAR(128) NOT NULL,
    lat           DOUBLE PRECISION,
    lon           DOUBLE PRECISION,
    temp          DOUBLE PRECISION,
    pressure_msl  DOUBLE PRECISION,
    humidity      DOUBLE PRECISION,
    dew_point     DOUBLE PRECISION,
    wind_speed    DOUBLE PRECISION,
    wind_dir      DOUBLE PRECISION,
    PRIMARY KEY (time, station)
);
SELECT create_hypertable('weather_obs', 'time', if_not_exists => TRUE);

-- Compression to keep long-term storage small (TimescaleDB native). ------------
ALTER TABLE precip_grid SET (timescaledb.compress, timescaledb.compress_segmentby = 'cell_x,cell_y');
SELECT add_compression_policy('precip_grid', INTERVAL '7 days', if_not_exists => TRUE);

ALTER TABLE location_readings SET (timescaledb.compress, timescaledb.compress_segmentby = 'location_id');
SELECT add_compression_policy('location_readings', INTERVAL '14 days', if_not_exists => TRUE);

ALTER TABLE weather_obs SET (timescaledb.compress, timescaledb.compress_segmentby = 'station');
SELECT add_compression_policy('weather_obs', INTERVAL '14 days', if_not_exists => TRUE);
