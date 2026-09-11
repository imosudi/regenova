-- ==============================================================================
-- REAMP EDGE BUFFER DATABASE SCHEMA
-- Migration: 001_initial_edge_schema.sql
-- Target Engine: SQLite 3 (Edge IPCs, Raspberry Pi, Industrial Gateways)
-- Purpose: Store-and-Forward local buffer during WAN outages (72 hours)
-- ==============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS edge_telemetry_buffer (
    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    sensor_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    quality TEXT NOT NULL DEFAULT 'VALID',
    confidence REAL NOT NULL DEFAULT 1.0,
    communication_status TEXT NOT NULL DEFAULT 'BUFFERED',
    buffered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now')),
    is_acknowledged INTEGER NOT NULL DEFAULT 0 CHECK (is_acknowledged IN (0, 1)),
    ack_received_at TEXT
);

-- Fast FIFO extraction index for cloud backfill streamer
CREATE INDEX IF NOT EXISTS idx_edge_buffer_fifo 
    ON edge_telemetry_buffer(is_acknowledged, sequence_id ASC);

-- Deduplication index preventing duplicate local sensor observations
CREATE UNIQUE INDEX IF NOT EXISTS idx_edge_buffer_unique_obs 
    ON edge_telemetry_buffer(tenant_id, asset_id, metric, timestamp);

-- Device metadata registry table for local edge configuration
CREATE TABLE IF NOT EXISTS edge_device_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
);

INSERT OR IGNORE INTO edge_device_config (config_key, config_value) VALUES 
    ('batch_flush_size', '1000'),
    ('max_buffer_retention_hours', '72'),
    ('compression_enabled', 'true'),
    ('heartbeat_interval_sec', '30');
