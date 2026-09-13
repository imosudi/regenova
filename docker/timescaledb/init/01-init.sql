-- =============================================================================
-- REGENOVA TimescaleDB Initialization Script
-- =============================================================================

-- 1. Enable Core Extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- 2. Create Canonical Telemetry Hypertable
CREATE TABLE IF NOT EXISTS telemetry (
    event_time TIMESTAMPTZ NOT NULL,
    ingestion_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_id UUID NOT NULL DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    site_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    component_id VARCHAR(64),
    sensor_id VARCHAR(64),
    metric VARCHAR(64) NOT NULL,
    value_numeric DOUBLE PRECISION,
    value_text TEXT,
    unit VARCHAR(32),
    quality VARCHAR(16) NOT NULL DEFAULT 'VALID',
    confidence REAL NOT NULL DEFAULT 1.0,
    communication_status VARCHAR(16) NOT NULL DEFAULT 'ONLINE',
    source VARCHAR(64) NOT NULL DEFAULT 'FLOWFIELD',
    schema_version VARCHAR(16) NOT NULL DEFAULT 'telemetry.v1',
    metadata JSONB DEFAULT '{}'::jsonb
);

SELECT create_hypertable(
    'telemetry',
    'event_time',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Indices for rapid slicing by tenant, asset, and time
CREATE INDEX IF NOT EXISTS idx_telemetry_tenant_metric_time 
    ON telemetry (tenant_id, metric, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_asset_time 
    ON telemetry (asset_id, event_time DESC);

-- 3. Configure Foreign Data Wrapper to Host PostgreSQL Server
CREATE SCHEMA IF NOT EXISTS host_regenova;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_foreign_server WHERE srvname = 'host_postgres') THEN
        CREATE SERVER host_postgres
        FOREIGN DATA WRAPPER postgres_fdw
        OPTIONS (host 'host.docker.internal', port '5432', dbname 'regenova_db');

        CREATE USER MAPPING FOR CURRENT_USER
        SERVER host_postgres
        OPTIONS (user 'regenova_db', password 'OmolileOtilile');
    END IF;

    -- Attempt schema import if host server is online
    BEGIN
        IMPORT FOREIGN SCHEMA public FROM SERVER host_postgres INTO host_regenova;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Foreign schema import deferred: %', SQLERRM;
    END;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Foreign server creation deferred: %', SQLERRM;
END $$;
