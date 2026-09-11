-- ==============================================================================
-- REAMP CANONICAL DATABASE SCHEMA
-- Migration: 001_initial_reamp_schema.sql
-- Target Engines: PostgreSQL 16+ & TimescaleDB 2.12+
-- Multi-Tenancy: Enforced via PostgreSQL Row Level Security (RLS)
-- ==============================================================================

-- 1. Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Notice: TimescaleDB extension is activated if installed in PostgreSQL instance
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
        CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;
    END IF;
END $$;

-- 2. Domain Hierarchy Tables (Levels 1 - 4)

CREATE TABLE IF NOT EXISTS organisations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) UNIQUE NOT NULL,
    billing_tier VARCHAR(32) NOT NULL DEFAULT 'ENTERPRISE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    organisation_id UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    region VARCHAR(128) NOT NULL,
    target_capacity_kw NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_portfolios_tenant ON portfolios(tenant_id);

CREATE TABLE IF NOT EXISTS sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    portfolio_id UUID NOT NULL REFERENCES portfolios(id) ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL CHECK (latitude >= -90.0 AND latitude <= 90.0),
    longitude NUMERIC(9, 6) NOT NULL CHECK (longitude >= -180.0 AND longitude <= 180.0),
    altitude_m NUMERIC(6, 1),
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    grid_voltage_kv NUMERIC(6, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sites_tenant ON sites(tenant_id);

-- 3. Plant Hierarchy Tables (Levels 5 - 8)

CREATE TABLE IF NOT EXISTS energy_systems (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    technology_type VARCHAR(32) NOT NULL CHECK (technology_type IN ('SOLAR_PV', 'WIND', 'BESS', 'HYBRID')),
    nameplate_capacity_kw NUMERIC(12, 2) NOT NULL CHECK (nameplate_capacity_kw > 0),
    lifecycle_state VARCHAR(32) NOT NULL DEFAULT 'PLANNED',
    technology_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_energy_systems_tenant ON energy_systems(tenant_id);
CREATE INDEX IF NOT EXISTS idx_energy_systems_tech ON energy_systems(technology_type);

CREATE TABLE IF NOT EXISTS assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    energy_system_id UUID NOT NULL REFERENCES energy_systems(id) ON DELETE CASCADE,
    parent_asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    asset_type VARCHAR(64) NOT NULL,
    lifecycle_state VARCHAR(32) NOT NULL DEFAULT 'PLANNED',
    manufacturer VARCHAR(128),
    model_number VARCHAR(128),
    serial_number VARCHAR(128),
    commissioning_date DATE,
    warranty_expiration DATE,
    technology_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_assets_tenant ON assets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_assets_system ON assets(energy_system_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);

CREATE TABLE IF NOT EXISTS components (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    parent_component_id UUID REFERENCES components(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    component_type VARCHAR(64) NOT NULL,
    lifecycle_state VARCHAR(32) NOT NULL DEFAULT 'OPERATIONAL',
    part_number VARCHAR(128),
    serial_number VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_components_tenant ON components(tenant_id);
CREATE INDEX IF NOT EXISTS idx_components_asset ON components(asset_id);

CREATE TABLE IF NOT EXISTS sensors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
    component_id UUID REFERENCES components(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) NOT NULL,
    sensor_type VARCHAR(64) NOT NULL,
    unit_of_measure VARCHAR(32) NOT NULL,
    sampling_interval_sec INTEGER NOT NULL DEFAULT 1 CHECK (sampling_interval_sec > 0),
    modbus_address VARCHAR(32),
    opc_node_id VARCHAR(128),
    mqtt_topic VARCHAR(255),
    min_physical_range NUMERIC(12, 4),
    max_physical_range NUMERIC(12, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_sensor_target CHECK (
        (asset_id IS NOT NULL AND component_id IS NULL) OR
        (asset_id IS NULL AND component_id IS NOT NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_sensors_tenant ON sensors(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sensors_type ON sensors(sensor_type);

-- 4. Canonical Telemetry Hypertable

CREATE TABLE IF NOT EXISTS telemetry_observations (
    timestamp TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    asset_id UUID NOT NULL,
    metric VARCHAR(64) NOT NULL,
    sensor_id UUID NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit VARCHAR(32) NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'SCADA',
    quality VARCHAR(16) NOT NULL DEFAULT 'VALID' CHECK (quality IN ('VALID', 'INVALID', 'MISSING', 'STALE', 'UNCERTAIN')),
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    communication_status VARCHAR(16) NOT NULL DEFAULT 'ONLINE' CHECK (communication_status IN ('ONLINE', 'DEGRADED', 'OFFLINE', 'BUFFERED')),
    PRIMARY KEY (timestamp, tenant_id, asset_id, metric)
);
CREATE INDEX IF NOT EXISTS idx_telemetry_tenant_metric ON telemetry_observations(tenant_id, metric, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_asset_time ON telemetry_observations(asset_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_quality ON telemetry_observations(quality);

-- Convert to TimescaleDB hypertable if TimescaleDB extension is active
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'create_hypertable') THEN
        PERFORM create_hypertable(
            'telemetry_observations',
            'timestamp',
            chunk_time_interval => INTERVAL '7 days',
            if_not_exists => TRUE
        );
    END IF;
END $$;

-- 5. Operations, CMMS & Maintenance Tables

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_tenant_time ON events(tenant_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS alarms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    sensor_id UUID REFERENCES sensors(id) ON DELETE SET NULL,
    alarm_code VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'ACKNOWLEDGED', 'CLEARED', 'SUPPRESSED')),
    severity VARCHAR(16) NOT NULL DEFAULT 'MEDIUM' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'EMERGENCY')),
    trigger_timestamp TIMESTAMPTZ NOT NULL,
    cleared_timestamp TIMESTAMPTZ,
    acknowledged_by UUID,
    acknowledged_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_alarms_tenant_status ON alarms(tenant_id, status);

CREATE TABLE IF NOT EXISTS anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    detection_timestamp TIMESTAMPTZ NOT NULL,
    detector_model VARCHAR(64) NOT NULL,
    anomaly_score REAL NOT NULL CHECK (anomaly_score >= 0.0 AND anomaly_score <= 1.0),
    root_cause_prediction JSONB NOT NULL DEFAULT '{}'::jsonb,
    shap_feature_importance JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW', 'TRIAGED', 'CONFIRMED_FAULT', 'FALSE_POSITIVE'))
);
CREATE INDEX IF NOT EXISTS idx_anomalies_tenant_time ON anomalies(tenant_id, detection_timestamp DESC);

CREATE TABLE IF NOT EXISTS work_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    anomaly_id UUID REFERENCES anomalies(id) ON DELETE SET NULL,
    order_number VARCHAR(64) UNIQUE NOT NULL,
    priority VARCHAR(16) NOT NULL DEFAULT 'P3_MEDIUM' CHECK (priority IN ('P1_CRITICAL', 'P2_HIGH', 'P3_MEDIUM', 'P4_LOW')),
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'PENDING_HITL_APPROVAL', 'APPROVED', 'DISPATCHED', 'COMPLETED', 'REJECTED')),
    recommended_action TEXT NOT NULL,
    estimated_labor_hours NUMERIC(6, 2),
    required_skill_level VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_work_orders_tenant_status ON work_orders(tenant_id, status);

CREATE TABLE IF NOT EXISTS maintenance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    component_id UUID REFERENCES components(id) ON DELETE SET NULL,
    work_order_id UUID REFERENCES work_orders(id) ON DELETE SET NULL,
    technician_name VARCHAR(128) NOT NULL,
    performed_at TIMESTAMPTZ NOT NULL,
    maintenance_type VARCHAR(32) NOT NULL CHECK (maintenance_type IN ('CORRECTIVE', 'PREVENTIVE', 'INSPECTION')),
    actions_taken TEXT NOT NULL,
    replaced_parts JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_maintenance_tenant ON maintenance_logs(tenant_id);

-- 6. Meteorological & Forecasting Tables

CREATE TABLE IF NOT EXISTS weather_observations (
    timestamp TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    ghi_w_per_m2 REAL CHECK (ghi_w_per_m2 >= 0.0 AND ghi_w_per_m2 <= 1500.0),
    poa_w_per_m2 REAL CHECK (poa_w_per_m2 >= 0.0 AND poa_w_per_m2 <= 1500.0),
    ambient_temp_c REAL CHECK (ambient_temp_c >= -50.0 AND ambient_temp_c <= 60.0),
    wind_speed_m_per_s REAL CHECK (wind_speed_m_per_s >= 0.0 AND wind_speed_m_per_s <= 70.0),
    wind_direction_deg REAL CHECK (wind_direction_deg >= 0.0 AND wind_direction_deg <= 360.0),
    relative_humidity_pct REAL CHECK (relative_humidity_pct >= 0.0 AND relative_humidity_pct <= 100.0),
    soiling_ratio REAL CHECK (soiling_ratio >= 0.0 AND soiling_ratio <= 1.0),
    PRIMARY KEY (timestamp, tenant_id, site_id)
);
CREATE INDEX IF NOT EXISTS idx_weather_tenant_site ON weather_observations(tenant_id, site_id, timestamp DESC);

CREATE TABLE IF NOT EXISTS generation_forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    energy_system_id UUID NOT NULL REFERENCES energy_systems(id) ON DELETE CASCADE,
    forecast_generated_at TIMESTAMPTZ NOT NULL,
    target_timestamp TIMESTAMPTZ NOT NULL,
    forecast_horizon_hours INTEGER NOT NULL,
    expected_power_kw NUMERIC(12, 2) NOT NULL,
    confidence_lower_p10_kw NUMERIC(12, 2),
    confidence_upper_p90_kw NUMERIC(12, 2),
    forecast_model VARCHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forecasts_system_target ON generation_forecasts(energy_system_id, target_timestamp);

-- 7. Analytics, Health & Financial Tables

CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    calculation_timestamp TIMESTAMPTZ NOT NULL,
    aggregation_period VARCHAR(16) NOT NULL CHECK (aggregation_period IN ('15MIN', '1HOUR', '1DAY', '1MONTH')),
    performance_ratio_stc REAL,
    power_coefficient_cp REAL,
    round_trip_efficiency_rte REAL,
    availability_factor_pct REAL
);
CREATE INDEX IF NOT EXISTS idx_perf_asset_time ON performance_metrics(asset_id, calculation_timestamp DESC);

CREATE TABLE IF NOT EXISTS health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    calculation_timestamp TIMESTAMPTZ NOT NULL,
    asset_health_index REAL NOT NULL CHECK (asset_health_index >= 0.0 AND asset_health_index <= 100.0),
    sub_index_thermal REAL,
    sub_index_electrical REAL,
    sub_index_mechanical REAL,
    sub_index_maintenance REAL,
    estimated_remaining_useful_life_days INTEGER
);
CREATE INDEX IF NOT EXISTS idx_health_asset_time ON health_scores(asset_id, calculation_timestamp DESC);

CREATE TABLE IF NOT EXISTS financial_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    lost_energy_kwh NUMERIC(14, 3) NOT NULL,
    applied_ppa_rate_per_mwh NUMERIC(8, 2) NOT NULL,
    financial_loss_amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    loss_attribution_category VARCHAR(64) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_financial_tenant_period ON financial_records(tenant_id, period_start, period_end);

-- 8. Identity & Immutable Audit Tables

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES organisations(tenant_id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('ADMIN', 'PORTFOLIO_MGR', 'OPERATOR', 'ENGINEER', 'AUDITOR')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    target_entity_type VARCHAR(64) NOT NULL,
    target_entity_id UUID NOT NULL,
    before_state JSONB,
    after_state JSONB,
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_logs(tenant_id, timestamp DESC);

-- 9. Multi-Tenant Row Level Security (RLS) Configuration

ALTER TABLE organisations ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE energy_systems ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE components ENABLE ROW LEVEL SECURITY;
ALTER TABLE sensors ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE alarms ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE weather_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE generation_forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Note: RLS isolation policy pattern for application tenant sessions
-- In production, application connections execute: SET LOCAL reamp.current_tenant_id = '<uuid>';
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
            'organisations', 'portfolios', 'sites', 'energy_systems', 'assets',
            'components', 'sensors', 'telemetry_observations', 'events', 'alarms',
            'anomalies', 'work_orders', 'maintenance_logs', 'weather_observations',
            'generation_forecasts', 'performance_metrics', 'health_scores',
            'financial_records', 'users', 'audit_logs'
          )
    LOOP
        EXECUTE format(
            'CREATE POLICY tenant_isolation_%I ON %I ' ||
            'FOR ALL TO PUBLIC ' ||
            'USING (tenant_id = NULLIF(current_setting(''reamp.current_tenant_id'', true), '''')::UUID) ' ||
            'WITH CHECK (tenant_id = NULLIF(current_setting(''reamp.current_tenant_id'', true), '''')::UUID);',
            tbl, tbl
        );
    END LOOP;
END $$;
