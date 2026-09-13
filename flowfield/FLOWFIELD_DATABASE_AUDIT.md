# REGENOVA FlowField — Database Audit (F0)

## 1. Database Infrastructure

- **DBMS**: PostgreSQL 18 Cluster (`postgresql@18-main.service`)
- **Host**: `127.0.0.1:5432` (or `db.regenova.cloud:5432` on local loopback)
- **Target Database**: `regenova_timeseries_db`
- **Owner Role**: `regenova_timeseries_db`
- **Password**: `OmolileOtilile`
- **Authentication**: `scram-sha-256` via `/etc/postgresql/18/main/pg_hba.conf`

---

## 2. TimescaleDB Extension Verification

Direct verification executed on server:
```sql
SELECT extname, extversion 
FROM pg_extension 
WHERE extname = 'timescaledb';
```

**Result (VERIFIED)**:
```text
   extname   | extversion 
-------------+------------
 timescaledb | 2.25.1
```
- Extension Edition: Apache 2 Edition
- Target Schema: `public`
- Status: Fully installed and active in `regenova_timeseries_db`.

---

## 3. Schema & Data Model Comparison

### Relational Metadata Database (`regenova_db`)
`regenova_db` holds asset metadata and transactional data. It currently contains:
- `telemetry_observations`: Standard PostgreSQL table with B-tree indices on `(timestamp, tenant_id, asset_id, metric)`, check constraints on `communication_status` and `quality`, and Row-Level Security (RLS) policies.
- Not optimized for high-throughput time-series chunk compression or continuous aggregates.

### Dedicated Time-Series Database (`regenova_timeseries_db`)
- Currently contains `0` user tables.
- A clean slate ready for the canonical FlowField hypertable.

---

## 4. Proposed FlowField Hypertable Specification (F3)

To be deployed during Phase F3:
```sql
CREATE TABLE IF NOT EXISTS telemetry (
    event_time TIMESTAMPTZ NOT NULL,
    ingestion_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_id UUID NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_telemetry_tenant_metric_time 
    ON telemetry (tenant_id, metric, event_time DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_asset_time 
    ON telemetry (asset_id, event_time DESC);

ALTER TABLE telemetry SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'tenant_id, asset_id, metric',
    timescaledb.compress_orderby = 'event_time DESC'
);
```

---

## 5. Security & Access Control
- `pg_hba.conf` allows connections from `127.0.0.1/32` for `all` databases using `scram-sha-256`.
- External access (`0.0.0.0/0`) is currently enabled only for `regenova_db`, keeping `regenova_timeseries_db` protected from unauthorized external access.

---

## 6. Database Verdict
- **Status**: `READY` for Phase F3 (PostgreSQL + TimescaleDB Migration & Pipeline Integration).
